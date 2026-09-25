"""Deterministic intake boundary for publicly licensed SoccerTrack v2 media.

The package verifies provenance and byte-level alignment between public video
assets and their BAS annotation containers.  It deliberately does not inspect
pixels, classify plays, invoke a model, or expose annotations to the visual
input or retrieval manifests.
"""

from .adapter import INTAKE_SCHEMA_VERSION

__all__ = ["INTAKE_SCHEMA_VERSION"]
