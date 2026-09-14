"""Node registry.

Node ids are namespaced with a Sloyd prefix so they cannot collide with other packs.
Changing an id breaks every saved workflow that uses it, so treat these as stable.
"""

from .generate_3d import SloydImageTo3D, SloydTextTo3D
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

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
