from pathlib import Path
import json
from typing import Optional

import cv2
import numpy as np

from app.core.storage import StorageManager
from app.engines.avatar.schemas import CharacterIdentityPack, FaceBox, Point2D


class CharacterIdentityManager:
    """
    Normalizes an uploaded character reference image into a canonical 1080x960
    lower-half frame, detects facial landmarks/anchors, and persists an
    immutable CharacterIdentityPack to guarantee identity consistency across segments.
    """

    TARGET_WIDTH = 1080
    TARGET_HEIGHT = 960

    def __init__(self, storage: Optional[StorageManager] = None) -> None:
        self.storage = storage or StorageManager()

    @classmethod
    def _fit_cover_1080x960(cls, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        scale = max(cls.TARGET_WIDTH / float(w), cls.TARGET_HEIGHT / float(h))
        new_w = int(round(w * scale))
        new_h = int(round(h * scale))
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

        # Center-horizontally, bias slightly upward vertically so head + upper body fit cleanly
        x0 = max(0, (new_w - cls.TARGET_WIDTH) // 2)
        y0 = max(0, min(new_h - cls.TARGET_HEIGHT, int((new_h - cls.TARGET_HEIGHT) * 0.25)))
        return resized[y0 : y0 + cls.TARGET_HEIGHT, x0 : x0 + cls.TARGET_WIDTH]

    @classmethod
    def _detect_face_box(cls, img: np.ndarray) -> FaceBox:
        if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data"):
            try:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                cascade = cv2.CascadeClassifier(cascade_path)
                faces = cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=4, minSize=(90, 90)
                )
                if len(faces) > 0:
                    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                    return FaceBox(x=int(x), y=int(y), w=int(w), h=int(h))
            except Exception:
                pass

        # Proportional upper-body portrait fallback for stylized/illustrated avatars
        fw = int(cls.TARGET_WIDTH * 0.30)
        fh = int(cls.TARGET_HEIGHT * 0.34)
        fx = (cls.TARGET_WIDTH - fw) // 2
        fy = int(cls.TARGET_HEIGHT * 0.14)
        return FaceBox(x=fx, y=fy, w=fw, h=fh)

    def build_identity_pack(
        self,
        character_id: str,
        project_id: str,
        raw_image_rel_path: str,
        approved: bool = False,
    ) -> CharacterIdentityPack:
        src_path = (self.storage.root / raw_image_rel_path).resolve()
        if not src_path.exists():
            raise FileNotFoundError(f"Character image not found: {src_path}")

        img = cv2.imread(str(src_path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Failed to decode character image: {src_path}")

        canonical = self._fit_cover_1080x960(img)
        face = self._detect_face_box(canonical)

        eye_left = Point2D(
            x=face.x + int(face.w * 0.34),
            y=face.y + int(face.h * 0.38),
        )
        eye_right = Point2D(
            x=face.x + int(face.w * 0.66),
            y=face.y + int(face.h * 0.38),
        )
        mouth_center = Point2D(
            x=face.x + int(face.w * 0.50),
            y=face.y + int(face.h * 0.75),
        )
        shoulder_y = min(self.TARGET_HEIGHT - 20, face.y + int(face.h * 1.35))
        color_mean = [round(float(v), 2) for v in cv2.mean(canonical)[:3]]

        pack_dir = self.storage.inputs_dir / project_id / "characters" / character_id
        pack_dir.mkdir(parents=True, exist_ok=True)
        canonical_path = pack_dir / "canonical_1080x960.png"
        cv2.imwrite(str(canonical_path), canonical)

        rel_canonical = str(canonical_path.relative_to(self.storage.root)).replace("\\", "/")
        pack = CharacterIdentityPack(
            character_id=character_id,
            canonical_image_path=rel_canonical,
            width=self.TARGET_WIDTH,
            height=self.TARGET_HEIGHT,
            face_box=face,
            eye_left=eye_left,
            eye_right=eye_right,
            mouth_center=mouth_center,
            shoulder_y=shoulder_y,
            color_mean_bgr=color_mean,
            approved=approved,
        )
        (pack_dir / "identity_pack.json").write_text(
            json.dumps(pack.model_dump(), indent=2), encoding="utf-8"
        )
        return pack
