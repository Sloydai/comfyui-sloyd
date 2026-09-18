"""Bridge: Sloyd model_path / SLOYD_JOB -> a model_3d File3D object.

The generation nodes output the downloaded GLB as a path string (plus a SLOYD_JOB
handle). ComfyUI's 3D preview and save nodes speak a File3D *object* type, not a
path, so a string cannot connect to them directly. This node converts either output
into a proper File3D so it wires straight into Preview 3D / Save 3D.

It uses the newer IO.ComfyNode schema API because File3D outputs are only expressible
through it; the rest of the pack uses the classic INPUT_TYPES style, which is fine,
ComfyUI supports both side by side.

If this API is unavailable (older ComfyUI without comfy_api.latest File3D support),
the module degrades: it exports nothing and the pack still loads. Users on such
builds fall back to Save Asset + the path output.
"""

from __future__ import annotations

import os

from .._compat import get_output_directory, logger

# These names are only present on ComfyUI builds new enough to have the File3D
# object system (roughly 0.3.40+). Guard the import so the pack still loads without it.
try:
    from comfy_api.latest import IO, Types  # type: ignore

    _HAVE_FILE3D = hasattr(IO, "File3DGLB") and hasattr(Types, "File3D")
except Exception:  # pragma: no cover - very old ComfyUI
    _HAVE_FILE3D = False


def _resolve_model_path(model_path: str, sloyd_job) -> str:
    """Pick the best available path from the two possible inputs and make it absolute."""
    candidate = ""
    # Prefer the job handle's stored absolute path when present; it is authoritative.
    if sloyd_job is not None:
        candidate = getattr(sloyd_job, "absolute_path", None) or getattr(
            sloyd_job, "relative_path", ""
        ) or ""
    if not candidate:
        candidate = (model_path or "").strip()
    if not candidate:
        raise ValueError(
            "Sloyd: no model to convert. Connect either 'model_path' or 'sloyd_job' "
            "from a Sloyd generation node."
        )

    path = candidate
    if not os.path.isabs(path):
        path = os.path.join(get_output_directory(), path)

    if not os.path.isfile(path):
        raise ValueError(
            f"Sloyd: model file not found at {path}. Re-run the generation node so the "
            "file is downloaded, then convert."
        )
    return path


if _HAVE_FILE3D:

    class SloydModelToFile3D(IO.ComfyNode):
        @classmethod
        def define_schema(cls):
            return IO.Schema(
                node_id="SloydModelToFile3D",
                display_name="Sloyd: Model to 3D File",
                category="Sloyd/Utility",
                description=(
                    "Convert a Sloyd model_path or SLOYD_JOB into a model_3d object that "
                    "plugs into Preview 3D (Advanced) and the Save 3D nodes."
                ),
                search_aliases=["sloyd preview", "sloyd model_3d", "sloyd glb to file3d"],
                inputs=[
                    IO.String.Input(
                        "model_path",
                        default="",
                        tooltip="model_path output from a Sloyd generation node.",
                    ),
                    IO.Custom("SLOYD_JOB").Input(
                        "sloyd_job",
                        optional=True,
                        tooltip="Alternatively, the sloyd_job output. Takes precedence if connected.",
                    ),
                ],
                outputs=[
                    IO.File3DGLB.Output(
                        display_name="model_3d",
                        tooltip="3D model object for Preview 3D (Advanced) / Save 3D.",
                    ),
                ],
            )

        @classmethod
        def execute(cls, model_path: str = "", sloyd_job=None) -> "IO.NodeOutput":
            path = _resolve_model_path(model_path, sloyd_job)
            logger.info("Sloyd: exposing %s as model_3d", path)
            return IO.NodeOutput(Types.File3D(path, file_format="glb"))

    SCHEMA_NODES = [SloydModelToFile3D]
else:  # pragma: no cover - old ComfyUI
    logger.warning(
        "Sloyd: this ComfyUI build lacks File3D support; the 'Model to 3D File' node "
        "is unavailable. Use 'Sloyd: Save Asset' and the model_path output instead."
    )
    SCHEMA_NODES = []
