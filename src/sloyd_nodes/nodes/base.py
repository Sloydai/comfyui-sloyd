"""Shared plumbing for the Sloyd nodes."""

from __future__ import annotations

import os
from typing import Any

from .._compat import get_output_directory, logger
from ..client import SloydClient
from ..credentials import SloydCredentials
from ..credentials import resolve as resolve_credentials

# Generated assets land in ComfyUI/output/sloyd/. Preview3D requires the model file
# to sit under the output directory and takes a path relative to it.
OUTPUT_SUBDIR = "sloyd"

CATEGORY_3D = "Sloyd/3D"
CATEGORY_ENV = "Sloyd/Environments"
CATEGORY_UTIL = "Sloyd/Utility"

TEXTURE_RESOLUTIONS = ["auto", "128", "256", "512", "1k", "2k", "4k", "none"]
TOPOLOGIES = ["auto", "quads", "triangles"]

MAX_FACE_COUNT = 500000
MAX_PROMPT_LENGTH = 4096

# Widget definition reused by every generation node. Sloyd has no seed parameter;
# this exists purely so ComfyUI's input hash changes when the user wants a re-roll.
# Without it a repeat queue press returns the cached result instead of a new model.
SEED_INPUT = (
    "INT",
    {
        "default": 0,
        "min": 0,
        "max": 0xFFFFFFFF,
        "control_after_generate": True,
        "tooltip": (
            "Forces the node to re-run so you get a fresh generation. Sloyd has no seed "
            "parameter, so this does not make results reproducible; it only busts the "
            "ComfyUI cache. Each re-run costs credits."
        ),
    },
)

TIMEOUT_INPUT = (
    "INT",
    {
        "default": 900,
        "min": 60,
        "max": 3600,
        "step": 30,
        "tooltip": "How long to wait for the job before giving up, in seconds.",
    },
)


def output_dir() -> str:
    path = os.path.join(get_output_directory(), OUTPUT_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def to_relative_output_path(absolute_path: str) -> str:
    """Path relative to ComfyUI/output, which is what Preview3D expects."""
    return os.path.relpath(absolute_path, get_output_directory()).replace(os.sep, "/")


def get_client(credentials: SloydCredentials | None) -> SloydClient:
    """Build a client from an explicit credential pair, or resolve one."""
    resolved = credentials or resolve_credentials()
    logger.debug("Sloyd: using credentials from %s (%s)", resolved.profile, resolved.redacted_id)
    return SloydClient(resolved)


def validate_prompt(prompt: str, *, required: bool, field: str = "prompt") -> str:
    cleaned = (prompt or "").strip()
    if required and not cleaned:
        raise ValueError(f"Sloyd needs a non-empty {field}.")
    if len(cleaned) > MAX_PROMPT_LENGTH:
        raise ValueError(
            f"Sloyd accepts up to {MAX_PROMPT_LENGTH} characters in {field}; got {len(cleaned)}."
        )
    return cleaned


def clamp_face_count(target_face_count: int) -> int:
    if target_face_count < 0:
        return 0
    if target_face_count > MAX_FACE_COUNT:
        logger.warning(
            "Sloyd: target_face_count %d exceeds the maximum %d; clamping.",
            target_face_count,
            MAX_FACE_COUNT,
        )
        return MAX_FACE_COUNT
    return target_face_count


def optional(value: Any) -> Any:
    """Normalise blank widget strings to None so they are omitted from the request."""
    if isinstance(value, str) and not value.strip():
        return None
    return value
