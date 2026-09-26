"""Evidence-gated SoccerMaster diagnostic protocol.

This package intentionally contains no VLM transport or event-recognition
code.  It prepares and validates a separately versioned, local-only protocol
whose future semantic calls must be explicitly authorized by the project
owner.  See :mod:`soccermaster_evidence_gated.pipeline`.
"""

from .pipeline import PROTOCOL_VERSION

__all__ = ["PROTOCOL_VERSION"]
