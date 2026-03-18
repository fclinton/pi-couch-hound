"""Training dataset management endpoints."""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import zipfile
from pathlib import Path

import cv2
from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from couch_hound.api.routes_snapshots import _sanitize_path
from couch_hound.api.schemas import (
    TrainingSampleCreateRequest,
    TrainingSampleFromEventRequest,
    TrainingSampleListResponse,
    TrainingSampleResponse,
    TrainingSampleUpdateRequest,
    TrainingStatsResponse,
)
from couch_hound.training_db import TrainingDatabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["training"])

TRAINING_IMAGES_DIR = Path("data/training_images")
TRAINING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
_RESOLVED_TRAINING_DIR = TRAINING_IMAGES_DIR.resolve()

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _get_training_db(request: Request) -> TrainingDatabase:
    db: TrainingDatabase | None = getattr(request.app.state, "training_db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Training database not available")
    return db


def _sample_to_response(sample: dict[str, object]) -> TrainingSampleResponse:
    sid = sample["id"]
    eid = sample["source_event_id"]
    conf = sample["confidence"]
    return TrainingSampleResponse(
        id=sid if isinstance(sid, int) else int(str(sid)),
        image_path=str(sample["image_path"]),
        label=str(sample["label"]),
        is_positive=bool(sample["is_positive"]),
        bbox=sample["bbox"] if isinstance(sample["bbox"], list) else None,
        confidence=float(str(conf)) if conf is not None else None,
        source=str(sample["source"]),
        source_event_id=eid if isinstance(eid, int) else None,
        notes=str(sample["notes"]) if sample["notes"] is not None else None,
        created_at=str(sample["created_at"]) if sample["created_at"] is not None else None,
    )


# ── CRUD ──


@router.get("/samples", response_model=TrainingSampleListResponse)
async def list_samples(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    label: str | None = None,
    is_positive: bool | None = None,
    source: str | None = None,
) -> TrainingSampleListResponse:
    """List training samples with optional filters."""
    db = _get_training_db(request)
    samples, total = await db.list_samples(
        limit=limit, offset=offset, label=label, is_positive=is_positive, source=source
    )
    return TrainingSampleListResponse(
        samples=[_sample_to_response(s) for s in samples],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/samples/{sample_id}", response_model=TrainingSampleResponse)
async def get_sample(request: Request, sample_id: int) -> TrainingSampleResponse:
    """Get a single training sample."""
    db = _get_training_db(request)
    sample = await db.get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    return _sample_to_response(sample)


@router.patch("/samples/{sample_id}", response_model=TrainingSampleResponse)
async def update_sample(
    request: Request, sample_id: int, body: TrainingSampleUpdateRequest
) -> TrainingSampleResponse:
    """Update a training sample's label or metadata."""
    db = _get_training_db(request)
    updated = await db.update_sample(
        sample_id,
        label=body.label,
        is_positive=body.is_positive,
        bbox=body.bbox,
        notes=body.notes,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    return _sample_to_response(updated)


@router.delete("/samples/{sample_id}")
async def delete_sample(request: Request, sample_id: int) -> dict[str, str]:
    """Delete a training sample and its image."""
    db = _get_training_db(request)
    sample = await db.delete_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")

    # Remove image file
    image_path = Path(str(sample["image_path"]))
    if image_path.is_file():
        image_path.unlink()

    return {"status": "deleted"}


# ── Create from event ──


@router.post(
    "/samples/from-event/{event_id}", status_code=201, response_model=TrainingSampleResponse
)
async def create_sample_from_event(
    request: Request, event_id: int, body: TrainingSampleFromEventRequest
) -> TrainingSampleResponse:
    """Create a training sample from an existing detection event."""
    from couch_hound.database import EventDatabase

    event_db: EventDatabase | None = getattr(request.app.state, "event_db", None)
    if event_db is None:
        raise HTTPException(status_code=503, detail="Event database not available")

    event = await event_db.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    db = _get_training_db(request)
    existing = await db.get_sample_by_event_id(event_id)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Event {event_id} already has a training sample (sample id {existing['id']})",
        )

    # Copy snapshot to training images directory — validate path stays within snapshots dir
    snapshot_path = event.get("snapshot_path")
    if not snapshot_path:
        raise HTTPException(status_code=400, detail="Event has no snapshot image")

    snapshots_base = str(Path("snapshots").resolve())
    src_resolved = os.path.normpath(os.path.realpath(str(snapshot_path)))
    if not src_resolved.startswith(snapshots_base) or not os.path.isfile(src_resolved):
        raise HTTPException(status_code=400, detail="Event has no valid snapshot image")

    src_name = os.path.basename(src_resolved)
    dest = _sanitize_path(f"event_{event_id}_{src_name}", _RESOLVED_TRAINING_DIR)
    shutil.copy2(src_resolved, dest)

    sample_id = await db.insert_sample(
        image_path=str(dest),
        label=str(event["label"]),
        is_positive=body.is_positive,
        bbox=event["bbox"] if isinstance(event["bbox"], list) else None,
        confidence=float(str(event["confidence"])) if event["confidence"] is not None else None,
        source="event",
        source_event_id=event_id,
        notes=body.notes,
    )

    sample = await db.get_sample(sample_id)
    assert sample is not None
    return _sample_to_response(sample)


# ── Upload image ──


@router.post("/samples/upload", status_code=201, response_model=TrainingSampleResponse)
async def upload_sample(
    request: Request,
    file: UploadFile,
    label: str = "dog",
    is_positive: bool = True,
) -> TrainingSampleResponse:
    """Upload an image as a training sample."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    import time

    safe_name = f"upload_{int(time.time() * 1000)}{ext}"
    dest = TRAINING_IMAGES_DIR / safe_name
    dest.write_bytes(content)

    db = _get_training_db(request)
    sample_id = await db.insert_sample(
        image_path=str(dest),
        label=label,
        is_positive=is_positive,
        source="upload",
    )

    sample = await db.get_sample(sample_id)
    assert sample is not None
    return _sample_to_response(sample)


# ── Capture from live feed ──


@router.post("/samples/capture", status_code=201, response_model=TrainingSampleResponse)
async def capture_sample(
    request: Request, body: TrainingSampleCreateRequest
) -> TrainingSampleResponse:
    """Capture the current camera frame as a training sample."""
    from couch_hound.pipeline import DetectionPipeline

    pipeline: DetectionPipeline | None = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Detection pipeline not available")

    frame = pipeline.last_frame
    if frame is None:
        raise HTTPException(status_code=503, detail="No frame available from camera")

    import time

    filename = f"capture_{int(time.time() * 1000)}.jpg"
    dest = TRAINING_IMAGES_DIR / filename
    cv2.imwrite(str(dest), frame)

    db = _get_training_db(request)
    sample_id = await db.insert_sample(
        image_path=str(dest),
        label=body.label,
        is_positive=body.is_positive,
        bbox=body.bbox,
        source="capture",
        notes=body.notes,
    )

    sample = await db.get_sample(sample_id)
    assert sample is not None
    return _sample_to_response(sample)


# ── Serve training images ──


@router.get("/images/{filename}")
async def get_training_image(filename: str) -> FileResponse:
    """Serve a training sample image."""
    safe_path = _sanitize_path(filename, _RESOLVED_TRAINING_DIR)
    if not os.path.isfile(safe_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(path=safe_path, media_type="image/jpeg")


# ── Stats ──


@router.get("/stats", response_model=TrainingStatsResponse)
async def get_stats(request: Request) -> TrainingStatsResponse:
    """Get training dataset statistics."""
    db = _get_training_db(request)
    stats = await db.get_stats()
    total = stats["total"]
    positive = stats["positive"]
    negative = stats["negative"]
    by_label = stats["by_label"]
    by_source = stats["by_source"]
    return TrainingStatsResponse(
        total=total if isinstance(total, int) else 0,
        positive=positive if isinstance(positive, int) else 0,
        negative=negative if isinstance(negative, int) else 0,
        by_label=by_label if isinstance(by_label, dict) else {},
        by_source=by_source if isinstance(by_source, dict) else {},
    )


# ── Export ──


@router.get("/export")
async def export_dataset(request: Request) -> StreamingResponse:
    """Export the training dataset as a ZIP with Pascal VOC annotations."""
    db = _get_training_db(request)
    samples = await db.get_all_samples()

    if not samples:
        raise HTTPException(status_code=400, detail="No training samples to export")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write manifest
        manifest = []
        for sample in samples:
            image_path = Path(str(sample["image_path"]))
            if not image_path.is_file():
                continue

            entry = {
                "filename": image_path.name,
                "label": str(sample["label"]),
                "is_positive": bool(sample["is_positive"]),
                "bbox": sample["bbox"],
                "confidence": sample["confidence"],
                "source": str(sample["source"]),
            }
            manifest.append(entry)

            # Add image to zip
            zf.write(str(image_path), f"images/{image_path.name}")

            # Generate Pascal VOC XML annotation if bbox exists
            bbox = sample["bbox"]
            if bbox and isinstance(bbox, list) and len(bbox) == 4:
                xml = _generate_voc_xml(
                    image_path.name,
                    str(sample["label"]),
                    bool(sample["is_positive"]),
                    bbox,
                )
                xml_name = image_path.stem + ".xml"
                zf.writestr(f"annotations/{xml_name}", xml)

        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=training_dataset.zip"},
    )


def _generate_voc_xml(
    filename: str,
    label: str,
    is_positive: bool,
    bbox: list[object],
) -> str:
    """Generate a minimal Pascal VOC XML annotation."""
    # bbox is normalized [x1, y1, x2, y2] in 0..1
    # We don't know the image dimensions here, so use normalized coords
    x1 = float(bbox[0])  # type: ignore[arg-type]
    y1 = float(bbox[1])  # type: ignore[arg-type]
    x2 = float(bbox[2])  # type: ignore[arg-type]
    y2 = float(bbox[3])  # type: ignore[arg-type]

    obj_name = label if is_positive else "background"

    return f"""\
<annotation>
  <filename>{filename}</filename>
  <object>
    <name>{obj_name}</name>
    <difficult>0</difficult>
    <bndbox>
      <xmin>{x1:.6f}</xmin>
      <ymin>{y1:.6f}</ymin>
      <xmax>{x2:.6f}</xmax>
      <ymax>{y2:.6f}</ymax>
    </bndbox>
  </object>
</annotation>"""
