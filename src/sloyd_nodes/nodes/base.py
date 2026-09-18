"""Shared plumbing for the Sloyd nodes."""

from __future__ import annotations

import os
from typing import Any

from .._compat import get_output_directory, logger
from ..client import SloydClient
from ..credentials import SloydCredentials
from ..credentials import resolve as resolve_credentials

# ComfyUI's current 3D nodes accept a File3D object over the FILE_3D_GLB socket.
# On builds that have it, generation nodes output that directly so model_3d connects
# to Preview 3D (Advanced) / Save 3D with no adapter node. On older builds we fall
# back to a plain path STRING so the pack still loads and Save Asset still works.
try:
    from comfy_api.latest import Types as _ComfyTypes  # type: ignore

    _File3D = _ComfyTypes.File3D
    MODEL_3D_TYPE = "FILE_3D_GLB"
except Exception:  # pragma: no cover - older ComfyUI
    _File3D = None
    MODEL_3D_TYPE = "STRING"


def build_model_3d(absolute_path: str):
    """Wrap a GLB path as the model_3d output value for the current ComfyUI.

    Returns a File3D object where supported, else the path string (older builds).
    """
    if _File3D is not None:
        return _File3D(absolute_path, file_format="glb")
    return to_relative_output_path(absolute_path)

# Generated assets land in ComfyUI/output/sloyd/. Preview3D requires the model file
# to sit under the output directory and takes a path relative to it.
OUTPUT_SUBDIR = "sloyd"

CATEGORY_3D = "Sloyd/3D"
CATEGORY_ENV = "Sloyd/Environments"
CATEGORY_2D = "Sloyd/2D"
CATEGORY_UTIL = "Sloyd/Utility"

TEXTURE_RESOLUTIONS = ["auto", "128", "256", "512", "1k", "2k", "4k", "none"]
TOPOLOGIES = ["auto", "quads", "triangles"]

MAX_FACE_COUNT = 500000
MAX_PROMPT_LENGTH = 4096

# Widget reused by every generation node. Sloyd has no seed parameter; this exists
# purely so ComfyUI's input hash changes when the user wants a fresh generation.
#
# Defaults to "fixed", NOT "randomize", on purpose. Every run of a Sloyd node costs
# credits and takes minutes. With "randomize" the widget rewrites itself after each
# run, so the input hash always changes and every upstream node re-executes and
# re-bills, which also makes chains like Text to 3D -> Retexture impossible to
# iterate on cheaply. With "fixed", ComfyUI serves the cached result and only the
# nodes you actually changed re-run. Bump the seed (or switch the widget to
# randomize) when you deliberately want a new generation.
SEED_INPUT = (
    "INT",
    {
        "default": 0,
        "min": 0,
        "max": 0xFFFFFFFF,
        "control_after_generate": "fixed",
        "tooltip": (
            "Change this to force a fresh generation (each one costs credits). Sloyd has "
            "no seed parameter, so this does not make results reproducible; it only busts "
            "the ComfyUI cache. Left alone, re-running reuses the cached result for free, "
            "which is what lets you iterate on a downstream node like Retexture."
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


def job_id_from_input(sloyd_job, job_id: str, node_label: str) -> str:
    """Resolve a source job id from either a SLOYD_JOB handle or a raw string.

    Model tools (retexture, split, skybox-edit, image-edit) operate on a job the
    caller already owns. Accepting both lets a user wire the upstream node's
    sloyd_job output *or* paste an id by hand.
    """
    if sloyd_job is not None:
        jid = getattr(sloyd_job, "job_id", None)
        if jid:
            return str(jid)
    jid = (job_id or "").strip()
    if jid:
        return jid
    raise ValueError(
        f"{node_label} needs a source job. Connect 'sloyd_job' from an upstream Sloyd "
        "node, or paste a job_id."
    )


# --- shared job completion --------------------------------------------------

from ..client import GLB_EXTENSIONS, skybox_panorama_url  # noqa: E402
from ..images import image_bytes_to_tensor  # noqa: E402
from ..types import (  # noqa: E402
    KIND_IMAGE,
    KIND_MODEL,
    KIND_SKYBOX,
    SloydJob,
)


def finish_model_job(client, job_id, endpoint, job, *, prompt=""):
    """Download a GLB result and package the standard 3D outputs.

    Returns (model_3d, sloyd_job, model_path, job_id).
    """
    absolute_path = client.download_asset_to_file(job_id, output_dir(), GLB_EXTENSIONS)
    relative_path = to_relative_output_path(absolute_path)
    logger.info("Sloyd: saved %s", relative_path)
    gen_params = job.get("genParams")
    handle = SloydJob(
        job_id=job_id,
        kind=KIND_MODEL,
        credentials=client.credentials,
        endpoint=endpoint,
        absolute_path=absolute_path,
        relative_path=relative_path,
        prompt=prompt,
        gen_params=gen_params if isinstance(gen_params, dict) else {},
    )
    return (build_model_3d(absolute_path), handle, relative_path, job_id)


def finish_skybox_job(client, job_id, endpoint, job, *, prompt=""):
    """Download a skybox panorama (from flatBoxData.panoramaUrl) and package outputs.

    Returns (skybox_image, sloyd_job, skybox_path, job_id).
    """
    panorama_url = skybox_panorama_url(job)
    content = client.download_url(panorama_url)
    extension = os.path.splitext(panorama_url.split("?")[0])[1] or ".webp"
    absolute_path = os.path.join(output_dir(), f"{job_id}_panorama{extension}")
    _atomic_write(absolute_path, content)
    relative_path = to_relative_output_path(absolute_path)
    logger.info("Sloyd: saved skybox %s", relative_path)
    gen_params = job.get("genParams")
    handle = SloydJob(
        job_id=job_id,
        kind=KIND_SKYBOX,
        credentials=client.credentials,
        endpoint=endpoint,
        absolute_path=absolute_path,
        relative_path=relative_path,
        prompt=prompt,
        gen_params=gen_params if isinstance(gen_params, dict) else {},
    )
    return (image_bytes_to_tensor(content), handle, relative_path, job_id)


# 2D image endpoints publish the result at jobs/{id}.png (also .jpeg/.webp).
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def finish_image_job(client, job_id, endpoint, job, *, prompt=""):
    """Download a 2D image result and package outputs.

    Returns (image, sloyd_job, image_path, job_id).
    """
    content, extension = client.download_asset(job_id, IMAGE_EXTENSIONS)
    absolute_path = os.path.join(output_dir(), f"{job_id}{extension}")
    _atomic_write(absolute_path, content)
    relative_path = to_relative_output_path(absolute_path)
    logger.info("Sloyd: saved image %s", relative_path)
    gen_params = job.get("genParams")
    handle = SloydJob(
        job_id=job_id,
        kind=KIND_IMAGE,
        credentials=client.credentials,
        endpoint=endpoint,
        absolute_path=absolute_path,
        relative_path=relative_path,
        prompt=prompt,
        gen_params=gen_params if isinstance(gen_params, dict) else {},
    )
    return (image_bytes_to_tensor(content), handle, relative_path, job_id)


def _atomic_write(path: str, content: bytes) -> None:
    tmp = f"{path}.part"
    with open(tmp, "wb") as handle:
        handle.write(content)
    os.replace(tmp, path)
