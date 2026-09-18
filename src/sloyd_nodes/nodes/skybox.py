"""360-degree skybox (worldbox) nodes: from text, from image, and edit.

All three return the equirectangular panorama as a normal ComfyUI IMAGE (from
flatBoxData.panoramaUrl in the job response), plus a SLOYD_JOB handle and the saved
path. The IMAGE flows into Save Image, upscalers, and community 360 viewers.
"""

from __future__ import annotations

import torch

from .._compat import logger
from ..images import tensor_to_png_bytes
from .base import (
    CATEGORY_ENV,
    SEED_INPUT,
    TIMEOUT_INPUT,
    finish_skybox_job,
    get_client,
    job_id_from_input,
    optional,
    validate_prompt,
)

RETURN_TYPES = ("IMAGE", "SLOYD_JOB", "STRING", "STRING")
RETURN_NAMES = ("skybox", "sloyd_job", "skybox_path", "job_id")

_GEN_STYLE_INPUT = (
    "STRING",
    {
        "default": "",
        "tooltip": "Optional Sloyd generation style ID. Blank uses the default. "
        "Valid IDs are listed under Generation Styles in the Sloyd API docs.",
    },
)


class SloydTextToSkybox:
    """POST /jobs/text-to-worldbox"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "a neon cyberpunk alley at night",
                        "tooltip": "Describe the 360-degree environment. Up to 4096 characters.",
                    },
                ),
                "seed": SEED_INPUT,
            },
            "optional": {
                "gen_style_id": _GEN_STYLE_INPUT,
                "timeout_seconds": TIMEOUT_INPUT,
            },
        }

    RETURN_TYPES = RETURN_TYPES
    RETURN_NAMES = RETURN_NAMES
    FUNCTION = "generate"
    CATEGORY = CATEGORY_ENV
    DESCRIPTION = "Generate a 360-degree equirectangular skybox from a text prompt using the Sloyd API."

    def generate(
        self,
        prompt: str,
        seed: int,
        gen_style_id: str = "",
        sloyd_credentials=None,
        timeout_seconds: int = 900,
    ):
        cleaned_prompt = validate_prompt(prompt, required=True)
        with get_client(sloyd_credentials) as client:
            job_id = client.create_job_json(
                "text-to-worldbox",
                {"prompt": cleaned_prompt, "genStyleId": optional(gen_style_id)},
            )
            logger.info("Sloyd text-to-worldbox job %s started", job_id)
            job = client.wait_for_job(job_id, float(timeout_seconds), "Sloyd skybox")
            return finish_skybox_job(client, job_id, "text-to-worldbox", job, prompt=cleaned_prompt)


class SloydSkyboxFromImage:
    """POST /jobs/image-upload -> POST /jobs/skybox-from-image"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": (
                    "IMAGE",
                    {"tooltip": "Source image to expand into a 360 environment. First frame only."},
                ),
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "Optional. How to expand the source into a full 360-degree "
                        "environment. Blank lets Sloyd decide.",
                    },
                ),
                "seed": SEED_INPUT,
            },
            "optional": {
                "gen_style_id": _GEN_STYLE_INPUT,
                "timeout_seconds": TIMEOUT_INPUT,
            },
        }

    RETURN_TYPES = RETURN_TYPES
    RETURN_NAMES = RETURN_NAMES
    FUNCTION = "generate"
    CATEGORY = CATEGORY_ENV
    DESCRIPTION = "Expand an image into a 360-degree equirectangular skybox using the Sloyd API."

    def generate(
        self,
        image: torch.Tensor,
        prompt: str,
        seed: int,
        gen_style_id: str = "",
        sloyd_credentials=None,
        timeout_seconds: int = 900,
    ):
        cleaned_prompt = validate_prompt(prompt, required=False)
        image_bytes = tensor_to_png_bytes(image)
        with get_client(sloyd_credentials) as client:
            image_job_id = client.upload_image(image_bytes, "skybox_source.png")
            logger.info("Sloyd: uploaded skybox source as image job %s", image_job_id)
            job_id = client.create_job_json(
                "skybox-from-image",
                {
                    "imageJobId": image_job_id,
                    "prompt": optional(cleaned_prompt),
                    "genStyleId": optional(gen_style_id),
                },
            )
            logger.info("Sloyd skybox-from-image job %s started", job_id)
            job = client.wait_for_job(job_id, float(timeout_seconds), "Sloyd skybox")
            return finish_skybox_job(client, job_id, "skybox-from-image", job, prompt=cleaned_prompt)


class SloydEditSkybox:
    """POST /jobs/skybox-edit"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "add a full moon",
                        "tooltip": "How to edit the existing skybox. Up to 4096 characters.",
                    },
                ),
                "seed": SEED_INPUT,
            },
            "optional": {
                "sloyd_job": ("SLOYD_JOB", {"tooltip": "Source skybox from an upstream Sloyd skybox node."}),
                "job_id": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Alternatively, paste a Sloyd skybox job id you own. "
                        "Ignored if sloyd_job is connected.",
                    },
                ),
                "gen_style_id": _GEN_STYLE_INPUT,
                "timeout_seconds": TIMEOUT_INPUT,
            },
        }

    RETURN_TYPES = RETURN_TYPES
    RETURN_NAMES = RETURN_NAMES
    FUNCTION = "run"
    CATEGORY = CATEGORY_ENV
    DESCRIPTION = "Edit an existing Sloyd skybox with a new prompt."

    def run(
        self,
        prompt: str,
        seed: int,
        sloyd_job=None,
        job_id: str = "",
        gen_style_id: str = "",
        sloyd_credentials=None,
        timeout_seconds: int = 900,
    ):
        cleaned_prompt = validate_prompt(prompt, required=True)
        source_id = job_id_from_input(sloyd_job, job_id, "Sloyd: Edit Skybox")
        with get_client(sloyd_credentials) as client:
            new_id = client.create_job_json(
                "skybox-edit",
                {"jobId": source_id, "prompt": cleaned_prompt, "genStyleId": optional(gen_style_id)},
            )
            logger.info("Sloyd skybox-edit job %s started (from %s)", new_id, source_id)
            job = client.wait_for_job(new_id, float(timeout_seconds), "Sloyd skybox edit")
            return finish_skybox_job(client, new_id, "skybox-edit", job, prompt=cleaned_prompt)
