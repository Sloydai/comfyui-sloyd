"""Thin shims over the ComfyUI runtime.

Every symbol here resolves to the real ComfyUI implementation when the package is
loaded inside ComfyUI. Outside ComfyUI (unit tests, linting, CI) the fallbacks let
the module import and the pure logic stay testable.
"""

from __future__ import annotations

import logging
import os
import tempfile

logger = logging.getLogger("sloyd")

# --- Output directory -------------------------------------------------------

try:  # pragma: no cover - exercised only inside ComfyUI
    import folder_paths  # type: ignore

    def get_output_directory() -> str:
        return folder_paths.get_output_directory()

    def get_input_directory() -> str:
        return folder_paths.get_input_directory()

except ImportError:  # pragma: no cover - fallback for standalone use
    _FALLBACK_ROOT = os.path.join(tempfile.gettempdir(), "sloyd_comfy")

    def get_output_directory() -> str:
        path = os.path.join(_FALLBACK_ROOT, "output")
        os.makedirs(path, exist_ok=True)
        return path

    def get_input_directory() -> str:
        path = os.path.join(_FALLBACK_ROOT, "input")
        os.makedirs(path, exist_ok=True)
        return path


# --- Progress reporting -----------------------------------------------------

try:  # pragma: no cover - exercised only inside ComfyUI
    from comfy.utils import ProgressBar as _ProgressBar  # type: ignore

    class ProgressBar:
        """Wraps comfy.utils.ProgressBar with an absolute 0-100 interface."""

        def __init__(self, total: int = 100) -> None:
            self._total = total
            self._bar = _ProgressBar(total)

        def set(self, value: int) -> None:
            self._bar.update_absolute(max(0, min(value, self._total)), self._total)

except ImportError:  # pragma: no cover - fallback for standalone use

    class ProgressBar:  # type: ignore[no-redef]
        def __init__(self, total: int = 100) -> None:
            self._total = total

        def set(self, value: int) -> None:
            return None


# --- Cancellation -----------------------------------------------------------

try:  # pragma: no cover - exercised only inside ComfyUI
    import comfy.model_management as _mm  # type: ignore

    def raise_if_cancelled() -> None:
        """Raise if the user pressed Cancel, so long polls stay interruptible."""
        _mm.throw_exception_if_processing_interrupted()

except ImportError:  # pragma: no cover - fallback for standalone use

    def raise_if_cancelled() -> None:
        return None
