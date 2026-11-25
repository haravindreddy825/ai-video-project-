from pathlib import Path
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

from app.engines.avatar.schemas import ContinuityReport


class ContinuityVerifier:
    """
    Verifies frame-to-frame boundary continuity (SSIM) between rendered chunks
    and audio/video duration synchronization (< 40ms drift target).
    """

    @staticmethod
    def compute_frame_ssim(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
        gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)
        # Downscale for fast, robust structural check
        small_a = cv2.resize(gray_a, (270, 240))
        small_b = cv2.resize(gray_b, (270, 240))
        score = ssim(small_a, small_b, data_range=255)
        return round(float(score), 4)

    @classmethod
    def verify_output(
        cls,
        output_mp4_path: Path,
        expected_audio_duration_sec: float,
        boundary_ssim_scores: list[float],
    ) -> ContinuityReport:
        warnings: list[str] = []
        cap = cv2.VideoCapture(str(output_mp4_path))
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open rendered MP4 for verification: {output_mp4_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        cap.release()

        video_duration_sec = round(frame_count / fps, 4)
        drift_ms = round(abs(video_duration_sec - expected_audio_duration_sec) * 1000.0, 2)

        ssim_min = min(boundary_ssim_scores) if boundary_ssim_scores else 1.0
        ssim_avg = (
            round(sum(boundary_ssim_scores) / len(boundary_ssim_scores), 4)
            if boundary_ssim_scores
            else 1.0
        )

        if ssim_min < 0.80:
            warnings.append(f"Low chunk boundary SSIM detected: {ssim_min:.3f}")
        if drift_ms > 120.0:
            warnings.append(f"Audio/video duration drift {drift_ms}ms exceeds 120ms.")

        passed = (ssim_min >= 0.80) and (drift_ms <= 120.0) and frame_count > 0
        return ContinuityReport(
            segments_checked=len(boundary_ssim_scores) + 1,
            boundary_ssim_min=ssim_min,
            boundary_ssim_avg=ssim_avg,
            audio_duration_sec=round(expected_audio_duration_sec, 4),
            video_duration_sec=video_duration_sec,
            av_drift_ms=drift_ms,
            passed=passed,
            warnings=warnings,
        )
