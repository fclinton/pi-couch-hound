"""Tests for template variable rendering."""

from __future__ import annotations

from couch_hound.templates import build_context, render_template


class TestRenderTemplate:
    def test_render_all_variables(self) -> None:
        template = "Dog {{label}} at {{timestamp}} conf={{confidence}}"
        context = {"label": "dog", "timestamp": "2026-01-01T00:00:00", "confidence": "0.9200"}
        result = render_template(template, context)
        assert result == "Dog dog at 2026-01-01T00:00:00 conf=0.9200"

    def test_render_no_templates_unchanged(self) -> None:
        assert render_template("plain text", {}) == "plain text"

    def test_render_missing_variable_replaced_empty(self) -> None:
        result = render_template("{{missing}}", {})
        assert result == ""

    def test_render_bbox_and_snapshot(self) -> None:
        context = {"bbox": "[0.1, 0.2, 0.3, 0.4]", "snapshot_path": "/snap/1.jpg"}
        result = render_template("{{bbox}} saved to {{snapshot_path}}", context)
        assert result == "[0.1, 0.2, 0.3, 0.4] saved to /snap/1.jpg"


class TestBuildContext:
    def test_build_context(self) -> None:
        ctx = build_context(
            label="dog",
            confidence=0.92,
            bbox=[0.1, 0.2, 0.3, 0.4],
            timestamp="2026-01-01T00:00:00",
            snapshot_path="/snap/1.jpg",
        )
        assert ctx["label"] == "dog"
        assert ctx["confidence"] == "0.9200"
        assert ctx["timestamp"] == "2026-01-01T00:00:00"
        assert ctx["snapshot_path"] == "/snap/1.jpg"
        assert "0.1" in ctx["bbox"]

    def test_build_context_default_snapshot(self) -> None:
        ctx = build_context(
            label="dog",
            confidence=0.5,
            bbox=[0.0, 0.0, 1.0, 1.0],
            timestamp="2026-01-01T00:00:00",
        )
        assert ctx["snapshot_path"] == ""
