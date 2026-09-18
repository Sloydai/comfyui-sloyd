"""Utility node: Save Asset.

Every generation node already auto-saves its result under ComfyUI/output/sloyd/ and
outputs a ready-to-view type (model_3d / IMAGE). This node is the one optional extra:
it copies a generated asset to a filename and location you choose.
"""

from __future__ import annotations

import os
import re
import shutil

from .._compat import get_output_directory, logger
from ..types import SloydJob
from .base import CATEGORY_UTIL, to_relative_output_path

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._/-]+")


class SloydSaveAsset:
    """Copies a generated asset to a chosen name under ComfyUI/output."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "sloyd_job": ("SLOYD_JOB",),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "sloyd/model",
                        "tooltip": "Output name relative to ComfyUI/output, without an extension. "
                        "A counter is appended when the name already exists.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_path",)
    FUNCTION = "save"
    CATEGORY = CATEGORY_UTIL
    OUTPUT_NODE = True
    DESCRIPTION = "Save a generated Sloyd asset under a chosen filename in ComfyUI/output."

    def save(self, sloyd_job: SloydJob, filename_prefix: str):
        source = sloyd_job.absolute_path
        if not source or not os.path.isfile(source):
            raise ValueError(
                f"Sloyd job {sloyd_job.job_id} has no downloaded file to save. "
                "Run the generation node again."
            )

        prefix = _UNSAFE_FILENAME.sub("_", (filename_prefix or "sloyd/model").strip("/ "))
        if not prefix:
            prefix = "sloyd/model"

        extension = os.path.splitext(source)[1]
        base_dir = get_output_directory()
        destination = os.path.join(base_dir, f"{prefix}{extension}")
        os.makedirs(os.path.dirname(destination), exist_ok=True)

        counter = 1
        while os.path.exists(destination):
            destination = os.path.join(base_dir, f"{prefix}_{counter:05d}{extension}")
            counter += 1

        shutil.copy2(source, destination)
        relative = to_relative_output_path(destination)
        logger.info("Sloyd: saved asset to %s", relative)
        return (relative,)
