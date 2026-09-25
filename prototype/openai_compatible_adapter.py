"""Fail-closed OpenAI-compatible adapter for approved loopback inference only."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


PLAYGROUND_RESPONSE_KEYS = [
    "answer",
    "confidence",
    "temporal_evidence_s",
    "spatial_evidence",
    "trajectory",
    "abstained",
    "abstention_reason",
]


class LocalOpenAICompatibleAdapter:
    """Validate a local OpenAI-compatible inference base URL before use."""

    def __init__(self, base_url: str, model: str) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("OpenAI-compatible endpoint must use a loopback host")
        if not model.strip():
            raise ValueError("model must be non-empty")
        self.base_url = base_url.rstrip("/")
        self.model = model

    def build_request(
        self, question: str, frame_data_urls: Sequence[str], tool_evidence: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """Build a non-executing chat-completions payload from caller-provided evidence."""
        if not question.strip():
            raise ValueError("question must be non-empty")
        if not frame_data_urls:
            raise ValueError("at least one sampled frame is required")
        if any(not frame.startswith("data:image/") for frame in frame_data_urls):
            raise ValueError("frames must be inline image data URLs; file and remote URLs are rejected")

        content: list[dict[str, Any]] = [{"type": "text", "text": question}]
        if tool_evidence is not None:
            content.append({
                "type": "text",
                "text": "Tool-derived evidence (verify against the frames; abstain if inconsistent): "
                + json.dumps(tool_evidence, sort_keys=True, separators=(",", ":")),
            })
        content.extend({"type": "image_url", "image_url": {"url": frame}} for frame in frame_data_urls)
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Answer only from supplied frames and evidence. Return JSON with answer, confidence, temporal_evidence_s, spatial_evidence, trajectory, abstained, and abstention_reason."},
                {"role": "user", "content": content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "playground_evidence_answer",
                    "strict": False,
                    "schema": {
                        "type": "object",
                        "required": PLAYGROUND_RESPONSE_KEYS,
                        "properties": {
                            "answer": {"type": "string"},
                            "confidence": {"type": ["number", "string"]},
                            "temporal_evidence_s": {},
                            "spatial_evidence": {},
                            "trajectory": {},
                            "abstained": {"type": "boolean"},
                            "abstention_reason": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
            },
        }
