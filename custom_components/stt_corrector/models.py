"""Runtime data models for STT Corrector integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class STTCorrectorRuntimeData:
    """Runtime data shared between proxy STT entity and sensor entities.

    Entity and sensor types will be narrowed in later chunks when
    CorrectedSTTEntity and sensor modules are created.
    """

    entity: Any = None
    sensors: list[Any] = field(default_factory=list)


@dataclass(slots=True)
class CorrectionStats:
    """Statistics emitted after each proxy STT invocation.

    Used by sensors to track correction activity.
    result_state values: "success", "no_speech", "error", "wrapped_unavailable"
    """

    result_state: str
    correction_applied: bool = False
    language: str = ""
    raw_text: str | None = None
    corrected_text: str | None = None
    processing_time_ms: float | None = None
    capture_device: str | None = None
