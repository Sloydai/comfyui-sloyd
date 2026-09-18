"""Node registry.

Node ids are namespaced with a Sloyd prefix so they cannot collide with other packs.
Changing an id breaks every saved workflow that uses it, so treat these as stable.
"""

from .generate_3d import SloydImageTo3D, SloydMultiImageTo3D, SloydTextTo3D
from .image_2d import SloydImageEdit, SloydSketchToImage, SloydTextToImage
from .model_tools import SloydRetexture, SloydSplitToParts
from .skybox import SloydEditSkybox, SloydSkyboxFromImage, SloydTextToSkybox
from .util import SloydSaveAsset

NODE_CLASS_MAPPINGS = {
    # 3D generation
    "SloydTextTo3D": SloydTextTo3D,
    "SloydImageTo3D": SloydImageTo3D,
    "SloydMultiImageTo3D": SloydMultiImageTo3D,
    # 3D model tools
    "SloydRetexture": SloydRetexture,
    "SloydSplitToParts": SloydSplitToParts,
    # Environments (360 skyboxes)
    "SloydTextToSkybox": SloydTextToSkybox,
    "SloydSkyboxFromImage": SloydSkyboxFromImage,
    "SloydEditSkybox": SloydEditSkybox,
    # 2D images
    "SloydTextToImage": SloydTextToImage,
    "SloydImageEdit": SloydImageEdit,
    "SloydSketchToImage": SloydSketchToImage,
    # Utility
    "SloydSaveAsset": SloydSaveAsset,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SloydTextTo3D": "Sloyd: Text to 3D",
    "SloydImageTo3D": "Sloyd: Image to 3D",
    "SloydMultiImageTo3D": "Sloyd: Multi-Image to 3D",
    "SloydRetexture": "Sloyd: Retexture",
    "SloydSplitToParts": "Sloyd: Split to Parts",
    "SloydTextToSkybox": "Sloyd: Text to Skybox",
    "SloydSkyboxFromImage": "Sloyd: Skybox from Image",
    "SloydEditSkybox": "Sloyd: Edit Skybox",
    "SloydTextToImage": "Sloyd: Text to Image",
    "SloydImageEdit": "Sloyd: Image Edit",
    "SloydSketchToImage": "Sloyd: Sketch to Image",
    "SloydSaveAsset": "Sloyd: Save Asset",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
