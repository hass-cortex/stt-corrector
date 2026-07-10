"""Capture-device identification and relay (chain-head side).

This proxy entity sits at the head of the STT chain, so it receives the
assist_pipeline's original audio stream — the ``PipelineRun`` bound async
generator whose frame locals identify the run and, through it, the
Assist satellite that recorded the audio. Because this entity buffers
the stream and forwards a replay generator, downstream entities (e.g.
cortex_stt) cannot introspect the original stream themselves; this
module therefore also *relays* the identified capture device to them via
a ``ContextVar`` shared through ``hass.data[CAPTURE_CONTEXT_KEY]``.
ContextVars propagate within the pipeline's asyncio task and stay
isolated between concurrent runs.

Shared contract: the ``CAPTURE_CONTEXT_KEY`` literal and the ContextVar
semantics must match the copy of this module vendored in the cortex_stt
integration.

Best-effort: introspection touches assist_pipeline internals; any shape
mismatch degrades to ``None`` and logs at debug level — the correction
pipeline is never affected.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

_LOGGER = logging.getLogger(__name__)

# Shared-contract key: this component sets the ContextVar stored under
# this hass.data key; downstream STT integrations read it.
CAPTURE_CONTEXT_KEY = "stt_capture_device_context"


def capture_context_var(hass: HomeAssistant) -> ContextVar[str | None]:
    """Return the shared capture-device ContextVar, creating it once."""
    var: ContextVar[str | None] | None = hass.data.get(CAPTURE_CONTEXT_KEY)
    if var is None:
        var = ContextVar("stt_capture_device", default=None)
        hass.data[CAPTURE_CONTEXT_KEY] = var
    return var


def capture_device_from_stream(hass: HomeAssistant, stream: Any) -> str | None:
    """Best-effort: name the assist satellite that recorded ``stream``.

    The assist_pipeline passes its ``PipelineRun._speech_to_text_stream``
    bound async generator as the STT audio stream; its frame locals hold
    the run, which knows the triggering device. Deterministic under
    concurrent runs (object identity, not timing). Must be called BEFORE
    the stream is consumed — an exhausted generator has no frame left.

    Returns a human-readable device name (device registry
    ``name_by_user`` / ``name``), falling back to the satellite entity id
    or raw device id. ``None`` when the stream shape is not recognized.
    """
    try:
        frame = getattr(stream, "ag_frame", None)
        if frame is None:
            return None
        run = frame.f_locals.get("self")
        if type(run).__name__ != "PipelineRun":
            return None
        device_id: str | None = getattr(run, "_device_id", None)
        satellite_id: str | None = getattr(run, "_satellite_id", None)
    except Exception:  # noqa: BLE001 — introspection must never break STT
        _LOGGER.debug("capture-device introspection failed", exc_info=True)
        return None

    if device_id:
        device = dr.async_get(hass).async_get(device_id)
        if device:
            return device.name_by_user or device.name or device_id
        return device_id
    if satellite_id:
        return satellite_id
    return None
