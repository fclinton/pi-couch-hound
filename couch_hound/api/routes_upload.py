"""File upload and listing endpoints for sounds and models."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from couch_hound.api.schemas import (
    ModelFileInfo,
    ModelListResponse,
    ModelUploadResponse,
    SoundFileInfo,
    SoundListResponse,
    SoundUploadResponse,
)

router = APIRouter(tags=["uploads"])

SOUNDS_DIR = Path("sounds")
MODELS_DIR = Path("models")

ALLOWED_SOUND_EXTENSIONS = {".wav", ".mp3"}
ALLOWED_MODEL_EXTENSION = ".tflite"
ALLOWED_LABELS_EXTENSION = ".txt"

MAX_SOUND_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_MODEL_SIZE = 50 * 1024 * 1024  # 50 MB


def _sanitize_filename(filename: str | None) -> str:
    """Strip directory components and reject invalid names."""
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    name = Path(filename).name
    if not name or name.startswith(".") or ".." in name:
        raise HTTPException(status_code=400, detail=f"Invalid filename: {filename}")
    return name


@router.post("/upload/sound", status_code=201, response_model=SoundUploadResponse)
async def upload_sound(file: UploadFile) -> SoundUploadResponse:
    """Upload a sound file (WAV/MP3) to the sounds directory."""
    filename = _sanitize_filename(file.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_SOUND_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_SOUND_EXTENSIONS))}"
            ),
        )

    content = await file.read()
    if len(content) > MAX_SOUND_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content)} bytes). Maximum: {MAX_SOUND_SIZE} bytes",
        )

    SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    dest = SOUNDS_DIR / filename
    dest.write_bytes(content)

    return SoundUploadResponse(filename=filename, path=str(dest), size=len(content))


@router.post("/upload/model", status_code=201, response_model=ModelUploadResponse)
async def upload_model(model: UploadFile, labels: UploadFile) -> ModelUploadResponse:
    """Upload a TFLite model and its labels file to the models directory."""
    model_name = _sanitize_filename(model.filename)
    labels_name = _sanitize_filename(labels.filename)

    if not model_name.lower().endswith(ALLOWED_MODEL_EXTENSION):
        raise HTTPException(
            status_code=400,
            detail=f"Model file must have '{ALLOWED_MODEL_EXTENSION}' extension",
        )
    if not labels_name.lower().endswith(ALLOWED_LABELS_EXTENSION):
        raise HTTPException(
            status_code=400,
            detail=f"Labels file must have '{ALLOWED_LABELS_EXTENSION}' extension",
        )

    model_content = await model.read()
    if len(model_content) > MAX_MODEL_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Model file too large ({len(model_content)} bytes). "
                f"Maximum: {MAX_MODEL_SIZE} bytes"
            ),
        )

    labels_content = await labels.read()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / model_name
    labels_path = MODELS_DIR / labels_name
    model_path.write_bytes(model_content)
    labels_path.write_bytes(labels_content)

    return ModelUploadResponse(model=str(model_path), labels=str(labels_path))


@router.get("/sounds", response_model=SoundListResponse)
async def list_sounds() -> SoundListResponse:
    """List available sound files."""
    sounds: list[SoundFileInfo] = []
    if SOUNDS_DIR.is_dir():
        for path in sorted(SOUNDS_DIR.iterdir()):
            if path.is_file() and path.suffix.lower() in ALLOWED_SOUND_EXTENSIONS:
                sounds.append(
                    SoundFileInfo(
                        filename=path.name,
                        path=str(path),
                        size=path.stat().st_size,
                    )
                )
    return SoundListResponse(sounds=sounds)


@router.get("/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    """List available TFLite models with their paired labels files."""
    models: list[ModelFileInfo] = []
    if MODELS_DIR.is_dir():
        for path in sorted(MODELS_DIR.iterdir()):
            if path.is_file() and path.suffix.lower() == ALLOWED_MODEL_EXTENSION:
                # Look for a matching labels file
                labels_path = path.with_suffix(ALLOWED_LABELS_EXTENSION)
                labels: str | None = str(labels_path) if labels_path.is_file() else None
                models.append(
                    ModelFileInfo(
                        filename=path.name,
                        path=str(path),
                        size=path.stat().st_size,
                        labels=labels,
                    )
                )
    return ModelListResponse(models=models)
