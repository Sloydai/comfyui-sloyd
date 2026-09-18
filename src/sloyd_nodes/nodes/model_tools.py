"""Model tool nodes: Retexture and Split to Parts.

Both operate on a 3D job the caller already owns. They accept the upstream node's
SLOYD_JOB handle (preferred) or a raw job_id string. Output matches the generation
nodes so results flow into Preview 3D (Advanced) / Save 3D with no adapter.
"""

from __future__ import annotations

from .._compat import logger
from .base import (
    CATEGORY_3D,
    MODEL_3D_TYPE,
    SEED_INPUT,
    TEXTURE_RESOLUTIONS,
    TIMEOUT_INPUT,
    finish_model_job,
    get_client,
    job_id_from_input,
    validate_prompt,
)

RETURN_TYPES = (MODEL_3D_TYPE, "SLOYD_JOB", "STRING", "STRING")
RETURN_NAMES = ("model_3d", "sloyd_job", "model_path", "job_id")

_SOURCE_INPUTS = {
    "sloyd_job": ("SLOYD_JOB", {"tooltip": "Source model from an upstream Sloyd 3D node."}),
    "job_id": (
        "STRING",
        {
            "default": "",
            "tooltip": "Alternatively, paste a Sloyd job id of a model you own. "
            "Ignored if sloyd_job is connected.",
        },
    ),
}


class SloydRetexture:
    """POST /jobs/retexture"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "glossy red ceramic glaze",
                        "tooltip": "Describe the new texture. Up to 4096 characters.",
                    },
                ),
                "texture_resolution": (
                    TEXTURE_RESOLUTIONS,
                    {"default": "auto", "tooltip": "Requested output texture resolution."},
                ),
                "seed": SEED_INPUT,
            },
            "optional": {
                **_SOURCE_INPUTS,
                "timeout_seconds": TIMEOUT_INPUT,
            },
        }

    RETURN_TYPES = RETURN_TYPES
    RETURN_NAMES = RETURN_NAMES
    FUNCTION = "run"
    CATEGORY = CATEGORY_3D
    DESCRIPTION = "Re-texture an existing Sloyd 3D model with a new prompt."

    def run(
        self,
        prompt: str,
        texture_resolution: str,
        seed: int,
        sloyd_job=None,
        job_id: str = "",
        sloyd_credentials=None,
        timeout_seconds: int = 900,
    ):
        cleaned_prompt = validate_prompt(prompt, required=True)
        source_id = job_id_from_input(sloyd_job, job_id, "Sloyd: Retexture")
        with get_client(sloyd_credentials) as client:
            new_id = client.create_job_json(
                "retexture",
                {
                    "jobId": source_id,
                    "prompt": cleaned_prompt,
                    "textureResolution": texture_resolution,
                },
            )
            logger.info("Sloyd retexture job %s started (from %s)", new_id, source_id)
            job = client.wait_for_job(new_id, float(timeout_seconds), "Sloyd retexture")
            return finish_model_job(client, new_id, "retexture", job, prompt=cleaned_prompt)


class SloydSplitToParts:
    """POST /jobs/split-to-parts

    Returns a single GLB containing the separated parts as distinct objects.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": SEED_INPUT,
            },
            "optional": {
                **_SOURCE_INPUTS,
                "timeout_seconds": TIMEOUT_INPUT,
            },
        }

    RETURN_TYPES = RETURN_TYPES
    RETURN_NAMES = RETURN_NAMES
    FUNCTION = "run"
    CATEGORY = CATEGORY_3D
    DESCRIPTION = (
        "Split an existing Sloyd 3D model into separate parts. Returns one GLB "
        "containing the parts as distinct objects."
    )

    def run(
        self,
        seed: int,
        sloyd_job=None,
        job_id: str = "",
        sloyd_credentials=None,
        timeout_seconds: int = 900,
    ):
        source_id = job_id_from_input(sloyd_job, job_id, "Sloyd: Split to Parts")
        with get_client(sloyd_credentials) as client:
            new_id = client.create_job_json("split-to-parts", {"jobId": source_id})
            logger.info("Sloyd split-to-parts job %s started (from %s)", new_id, source_id)
            job = client.wait_for_job(new_id, float(timeout_seconds), "Sloyd split-to-parts")
            return finish_model_job(client, new_id, "split-to-parts", job)
