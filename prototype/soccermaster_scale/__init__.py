"""Standalone soccer-only research package for scaled SoccerNet experiments.

This package deliberately owns its taxonomy, data contract, feature extraction,
training, evaluation, and reporting code.  It does not import the football or
multi-sport demo implementations.
"""

from .taxonomy import CLASS_NAMES, SOCCERNET_TO_CLASS

__all__ = ["CLASS_NAMES", "SOCCERNET_TO_CLASS"]

