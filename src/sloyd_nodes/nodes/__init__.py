"""Node registry.

Node ids are namespaced with a Sloyd prefix so they cannot collide with other packs.
Changing an id breaks every saved workflow that uses it, so treat these as stable.
"""

from .generate_3d import SloydImageTo3D, SloydTextTo3D
from .preview_bridge import SCHEMA_NODES
from .skybox import SloydSkyboxFromImage
from .util import SloydCredentialsNode, SloydJobInfo, SloydSaveAsset

NODE_CLASS_MAPPINGS = {
    "SloydTextTo3D": SloydTextTo3D,
    "SloydImageTo3D": SloydImageTo3D,
    "SloydSkyboxFromImage": SloydSkyboxFromImage,
    "SloydCredentials": SloydCredentialsNode,
    "SloydSaveAsset": SloydSaveAsset,
    "SloydJobInfo": SloydJobInfo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SloydTextTo3D": "Sloyd: Text to 3D",
    "SloydImageTo3D": "Sloyd: Image to 3D",
    "SloydSkyboxFromImage": "Sloyd: Skybox from Image",
    "SloydCredentials": "Sloyd: Credentials",
    "SloydSaveAsset": "Sloyd: Save Asset",
    "SloydJobInfo": "Sloyd: Job Info",
}

# Schema-API nodes (IO.ComfyNode) self-describe via node_id/display_name, so they are
# registered by class rather than by a hand-written display-name entry. Only present
# on ComfyUI builds new enough to support File3D outputs.
for _node in SCHEMA_NODES:
    NODE_CLASS_MAPPINGS[_node.define_schema().node_id] = _node

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
