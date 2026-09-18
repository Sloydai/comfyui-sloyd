"""Text-to-3D and Image-to-3D generation nodes.

Both emit the same outputs:

    MODEL_3D     (FILE_3D_GLB) plugs straight into Preview 3D (Advanced) / Save 3D
    SLOYD_JOB    typed handle, chains into Retexture / Split to Parts
    STRING       model path relative to ComfyUI/output, for Save Asset / external use
    STRING       raw job id, for logging or an external pipeline
"""

from __future__ import annotations

import torch

from .._compat import logger
from ..client import GLB_EXTENSIONS
from ..images import tensor_to_png_bytes
from ..types import KIND_MODEL, SloydJob
from .base import (
    CATEGORY_3D,
    SEED_INPUT,
    TEXTURE_RESOLUTIONS,
    TIMEOUT_INPUT,
    TOPOLOGIES,
    build_model_3d,
    clamp_face_count,
    get_client,
    output_dir,
    to_relative_output_path,
    validate_prompt,
)

# model_3d is the FILE_3D_GLB socket that current ComfyUI 3D nodes accept. Falls back
# to a plain string on older builds without the File3D type (see base.MODEL_3D_TYPE).
from .base import MODEL_3D_TYPE

RETURN_TYPES = (MODEL_3D_TYPE, "SLOYD_JOB", "STRING", "STRING")
RETURN_NAMES = ("model_3d", "sloyd_job", "model_path", "job_id")


def _finish(client, job_id: str, endpoint: str, credentials, prompt: str, job: dict):
    """Download the finished GLB and package the outputs."""
    absolute_path = client.download_asset_to_file(job_id, output_dir(), GLB_EXTENSIONS)
    relative_path = to_relative_output_path(absolute_path)
    logger.info("Sloyd: saved %s", relative_path)

    gen_params = job.get("genParams")
    sloyd_job = SloydJob(
        job_id=job_id,
        kind=KIND_MODEL,
        credentials=credentials,
        endpoint=endpoint,
        absolute_path=absolute_path,
        relative_path=relative_path,
        prompt=prompt,
        gen_params=gen_params if isinstance(gen_params, dict) else {},
    )
    model_3d = build_model_3d(absolute_path)
    return (model_3d, sloyd_job, relative_path, job_id)


class SloydTextTo3D:
    """POST /jobs/text-to-3d"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "a medieval knight helmet",
                        "tooltip": "What to generate. Up to 4096 characters.",
                    },
                ),
                "topology": (
                    TOPOLOGIES,
                    {"default": "auto", "tooltip": "Mesh topology of the output."},
                ),
                "target_face_count": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 500000,
                        "step": 1000,
                        "tooltip": "0 lets the Sloyd pipeline choose. Maximum 500000.",
                    },
                ),
                "texture_resolution": (
                    TEXTURE_RESOLUTIONS,
                    {
                        "default": "auto",
                        "tooltip": "'none' produces a geometry-only model with no texture.",
                    },
                ),
                "t_pose": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Generate in a neutral T-pose. Useful if you plan to rig or animate.",
                    },
                ),
                "seed": SEED_INPUT,
            },
            "optional": {
                "sloyd_credentials": ("SLOYD_CREDENTIALS",),
                "timeout_seconds": TIMEOUT_INPUT,
            },
        }

    RETURN_TYPES = RETURN_TYPES
    RETURN_NAMES = RETURN_NAMES
    FUNCTION = "generate"
    CATEGORY = CATEGORY_3D
    DESCRIPTION = "Generate a 3D model (GLB) from a text prompt using the Sloyd API."

    def generate(
        self,
        prompt: str,
        topology: str,
        target_face_count: int,
        texture_resolution: str,
        t_pose: bool,
        seed: int,
        sloyd_credentials=None,
        timeout_seconds: int = 900,
    ):
        cleaned_prompt = validate_prompt(prompt, required=True)

        with get_client(sloyd_credentials) as client:
            job_id = client.create_job_json(
                "text-to-3d",
                {
                    "prompt": cleaned_prompt,
                    "topology": topology,
                    "targetFaceCount": clamp_face_count(target_face_count),
                    "textureResolution": texture_resolution,
                    "tPose": t_pose,
                },
            )
            logger.info("Sloyd text-to-3d job %s started", job_id)
            job = client.wait_for_job(job_id, float(timeout_seconds), "Sloyd text-to-3d")
            return _finish(
                client, job_id, "text-to-3d", client.credentials, cleaned_prompt, job
            )


class SloydImageTo3D:
    """POST /jobs/image-to-3d"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Reference image. Only the first frame of a batch is used."}),
                "topology": (
                    TOPOLOGIES,
                    {"default": "auto", "tooltip": "Mesh topology of the output."},
                ),
                "target_face_count": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 500000,
                        "step": 1000,
                        "tooltip": "0 lets the Sloyd pipeline choose. Maximum 500000.",
                    },
                ),
                "texture_resolution": (
                    TEXTURE_RESOLUTIONS,
                    {
                        "default": "auto",
                        "tooltip": "'none' produces a geometry-only model with no texture.",
                    },
                ),
                "seed": SEED_INPUT,
            },
            "optional": {
                "sloyd_credentials": ("SLOYD_CREDENTIALS",),
                "timeout_seconds": TIMEOUT_INPUT,
            },
        }

    RETURN_TYPES = RETURN_TYPES
    RETURN_NAMES = RETURN_NAMES
    FUNCTION = "generate"
    CATEGORY = CATEGORY_3D
    DESCRIPTION = "Generate a 3D model (GLB) from a single reference image using the Sloyd API."

    def generate(
        self,
        image: torch.Tensor,
        topology: str,
        target_face_count: int,
        texture_resolution: str,
        seed: int,
        sloyd_credentials=None,
        timeout_seconds: int = 900,
    ):
        image_bytes = tensor_to_png_bytes(image)

        with get_client(sloyd_credentials) as client:
            job_id = client.create_job_multipart(
                "image-to-3d",
                files={"file": ("input.png", image_bytes, "image/png")},
                data={
                    "topology": topology,
                    "targetFaceCount": clamp_face_count(target_face_count),
                    "textureResolution": texture_resolution,
                },
            )
            logger.info("Sloyd image-to-3d job %s started", job_id)
            job = client.wait_for_job(job_id, float(timeout_seconds), "Sloyd image-to-3d")
            return _finish(client, job_id, "image-to-3d", client.credentials, "", job)
