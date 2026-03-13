"""Download the default MobileNet SSD v2 (COCO) TFLite model and labels."""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path("models")

MODEL_URL = (
    "https://storage.googleapis.com/download.tensorflow.org/models"
    "/tflite/coco_ssd_mobilenet_v2_quantized_2018_06_29.zip"
)
MODEL_FILENAME = "ssd_mobilenet_v2.tflite"
MODEL_SHA256 = None  # Set after first verified download if pinning is desired

LABELS_URL = "https://raw.githubusercontent.com/google-coral/test_data/master/coco_labels.txt"
LABELS_FILENAME = "coco_labels.txt"


def _download(url: str, dest: Path) -> None:
    """Download a file with a progress indicator."""
    print(f"  Downloading {url}")
    try:
        urllib.request.urlretrieve(url, dest, _report_progress)  # noqa: S310
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise SystemExit(f"Download failed: {exc}") from exc
    print()


def _report_progress(block_num: int, block_size: int, total_size: int) -> None:
    if total_size > 0:
        pct = min(100, block_num * block_size * 100 // total_size)
        print(f"\r  Progress: {pct}%", end="", flush=True)


def _extract_tflite_from_zip(zip_path: Path, dest: Path) -> None:
    """Extract the .tflite file from the downloaded zip archive."""
    import zipfile

    with zipfile.ZipFile(zip_path) as zf:
        tflite_names = [n for n in zf.namelist() if n.endswith(".tflite")]
        if not tflite_names:
            raise SystemExit("No .tflite file found in downloaded archive")
        # Extract the first .tflite file found
        with zf.open(tflite_names[0]) as src, open(dest, "wb") as dst:
            dst.write(src.read())


def _verify_sha256(path: Path, expected: str) -> bool:
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return sha == expected


def setup() -> None:
    """Download model and labels to the models/ directory."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODELS_DIR / MODEL_FILENAME
    labels_path = MODELS_DIR / LABELS_FILENAME

    # ── Model ─────────────────────────────────────────
    if model_path.exists():
        print(f"Model already exists: {model_path}")
    else:
        print(f"Downloading detection model to {model_path} ...")
        zip_path = MODELS_DIR / "model_download.zip"
        try:
            _download(MODEL_URL, zip_path)
            _extract_tflite_from_zip(zip_path, model_path)
        finally:
            zip_path.unlink(missing_ok=True)

        if MODEL_SHA256 and not _verify_sha256(model_path, MODEL_SHA256):
            model_path.unlink(missing_ok=True)
            raise SystemExit("Model checksum verification failed")

        print(f"  Saved: {model_path} ({model_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # ── Labels ────────────────────────────────────────
    if labels_path.exists():
        print(f"Labels already exist: {labels_path}")
    else:
        print(f"Downloading labels to {labels_path} ...")
        _download(LABELS_URL, labels_path)
        line_count = len(labels_path.read_text().splitlines())
        print(f"  Saved: {labels_path} ({line_count} labels)")

    print("Model setup complete.")


if __name__ == "__main__":
    setup()
    sys.exit(0)
