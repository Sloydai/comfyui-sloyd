"""Sloyd AI nodes for ComfyUI.

Entry point ComfyUI loads. Exposes the node mappings and the web extension that
adds the Sloyd credential fields to the Settings panel.
"""

from .src.sloyd_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .src.sloyd_nodes.server_routes import register_routes

# Serves web/ to the ComfyUI frontend.
WEB_DIRECTORY = "./web"

register_routes()

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
