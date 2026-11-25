"""
End-to-End Playwright Release Test against live Next.js (127.0.0.1:3000)
and FastAPI (127.0.0.1:8000).

Tests:
  Login -> Create Project -> Write Script -> Generate Audio ->
  Upload/Approve Character -> Generate Avatar -> Generate Visuals ->
  Export 1080x1920 MP4 -> Preview -> Download -> Validate MP4.
"""
from pathlib import Path
import sys
import tempfile
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))
from app.engines.compositor.validation import ExportValidator


THIRTY_SEC_SCRIPT = (
    "Have you ever wondered how computers understand human language? "
    "Modern language models break sentences into small pieces called tokens. "
    "For example, a single word might become one or two tokens depending on how common it is. "
    "Next, each token is converted into a list of numbers known as an embedding vector. "
    "Because similar words have similar vectors, the model can measure meaning mathematically. "
    "In summary, embeddings turn text into geometry so machines can reason."
)


def _create_test_portrait(path: Path) -> None:
    img = Image.new("RGB", (720, 960), color=(32, 42, 62))
    draw = ImageDraw.Draw(img)
    draw.ellipse([160, 560, 560, 1020], fill=(45, 95, 160))
    draw.rectangle([320, 470, 400, 600], fill=(228, 185, 155))
    draw.ellipse([235, 200, 485, 500], fill=(235, 192, 162))
    draw.pieslice([225, 175, 495, 360], start=180, end=360, fill=(45, 35, 30))
    draw.ellipse([295, 315, 330, 340], fill=(255, 255, 255))
    draw.ellipse([390, 315, 425, 340], fill=(255, 255, 255))
    draw.ellipse([307, 321, 320, 334], fill=(35, 30, 30))
    draw.ellipse([402, 321, 415, 334], fill=(35, 30, 30))
    draw.arc([325, 405, 395, 440], start=10, end=170, fill=(165, 65, 70), width=5)
    img.save(path, format="PNG")


def main() -> None:
    console_errors: list[str] = []
    page_errors: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        portrait_path = tmp_dir / "e2e_portrait.png"
        _create_test_portrait(portrait_path)
        downloaded_mp4 = tmp_dir / "downloaded_release.mp4"

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            # 1. Dashboard & Login flow
            page.goto("http://127.0.0.1:3000", wait_until="networkidle")
            assert page.get_by_text("Educational Video Projects").is_visible()

            # Sign out & Sign in via UI modal
            page.get_by_title("Sign out").click()
            page.get_by_role("button", name="Sign In").click()
            page.locator("input[type='password']").fill("studio-local")
            page.locator("form button[type='submit']").click()
            page.get_by_title("Sign out").wait_for(state="visible", timeout=10000)
            print("[OK] 1. Dashboard loaded & Login flow verified")

            # 2. Create Project
            page.get_by_role("button", name="New Video Project").click()
            page.get_by_placeholder("e.g. How Neural Networks Learn").fill("Playwright Release E2E")
            page.get_by_role("button", name="Create Project").click()
            page.get_by_text("Playwright Release E2E").first.wait_for(state="visible", timeout=10000)

            # Open Studio for the newly created project
            card = page.locator("div.rounded-2xl", has_text="Playwright Release E2E").first
            card.get_by_role("link", name="Open Studio").click()
            page.wait_for_url("**/projects/*", timeout=10000)
            print("[OK] 2. Project created & Studio opened")

            # 3. Write Script & Generate Audio
            page.locator("textarea").fill(THIRTY_SEC_SCRIPT)
            page.get_by_role("button", name="Save Script & Generate Audio").click()
            page.locator("audio").wait_for(state="visible", timeout=90000)
            print("[OK] 3. Script saved, Audio generated & <audio> preview visible")

            # 4. Upload Character & Generate Avatar
            page.get_by_role("button", name="2. Character & Avatar").click()
            page.locator("input[type='file']").set_input_files(str(portrait_path))
            page.get_by_role("button", name="Upload & Approve Character").click()
            page.get_by_text("Approved").first.wait_for(state="visible", timeout=15000)

            page.get_by_role("button", name="Generate Synchronized Avatar").click()
            page.locator("video").first.wait_for(state="visible", timeout=120000)
            print("[OK] 4. Character approved, Avatar generated & <video> preview visible")

            # 5. Generate Educational Visuals
            page.get_by_role("button", name="3. Visuals").click()
            page.get_by_role("button", name="Generate Visual Scenes from Audio").click()
            page.get_by_text("Scene #1").wait_for(state="visible", timeout=90000)
            print("[OK] 5. Educational Visuals generated & scene previews rendered")

            # 6. Export Final 1080x1920 MP4, Preview & Download
            page.get_by_role("button", name="4. Progress & Export").click()
            page.get_by_role("button", name="Export Final 1080×1920 MP4").click()
            dl_link = page.get_by_role("link", name="Download Final MP4")
            dl_link.wait_for(state="visible", timeout=180000)

            # Verify final MP4 preview video element is playable in browser
            preview_video = page.locator("video").first
            preview_video.wait_for(state="visible", timeout=15000)
            dur_text = page.locator("text=/\\d+\\.\\d+s • 1080×1920/").first.inner_text()
            actual_dur = float(dur_text.split("s")[0].strip())

            with page.expect_download(timeout=30000) as dl_info:
                dl_link.click()
            download = dl_info.value
            download.save_as(str(downloaded_mp4))
            assert downloaded_mp4.exists() and downloaded_mp4.stat().st_size > 50000

            report = ExportValidator.validate(downloaded_mp4, expected_audio_duration_sec=actual_dur)
            assert report.passed, f"Downloaded MP4 validation failed: {report}"
            print(
                f"[OK] 6. Downloaded MP4 verified: {report.width}x{report.height} "
                f"{report.fps}fps {report.video_codec}/{report.audio_codec} "
                f"dur={report.duration_sec}s drift={report.av_drift_ms}ms"
            )

            # Clean up only the E2E test project via Dashboard Delete
            page.goto("http://127.0.0.1:3000", wait_until="networkidle")
            page.on("dialog", lambda d: d.accept())
            test_card = page.locator("div.rounded-2xl", has_text="Playwright Release E2E").first
            test_card.get_by_title("Delete project").click()
            page.wait_for_timeout(1000)

            browser.close()

    assert not page_errors, f"Page errors detected: {page_errors}"
    assert not console_errors, f"Console errors detected: {console_errors}"
    print("[SUCCESS] Full Playwright E2E release test passed with 0 console/page errors!")


if __name__ == "__main__":
    main()
