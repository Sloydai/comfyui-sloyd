#!/usr/bin/env python3
"""Generate the example workflows in example_workflows/.

Run after changing any node's inputs:

    python scripts/generate_example_workflows.py

Why this is generated rather than hand-written: a workflow's ``widgets_values`` is a
positional array that must line up with the node's input order, and a seed widget
contributes a second entry for its control_after_generate mode. Inserting one new
widget silently shifts every value after it, so hand-edited examples rot quietly.

Sloyd node definitions are read from the local package (not a running server) so this
always reflects the code in the repo. Non-Sloyd node shapes are declared below, since
they come from ComfyUI core.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "example_workflows")

WIDGET_SCALARS = {"STRING", "INT", "FLOAT", "BOOLEAN"}

# Shapes for the ComfyUI core nodes used in the examples. Kept minimal: only what the
# workflow format needs. Types must match what core actually exposes.
CORE = {
    "LoadImage": {
        "widgets": ["example.png", "image"],
        "inputs": [],
        "outputs": [("IMAGE", "IMAGE"), ("MASK", "MASK")],
    },
    "PreviewImage": {
        "widgets": [],
        "inputs": [("images", "IMAGE")],
        "outputs": [],
    },
    "Preview3DAdvanced": {
        "widgets": [1024, 1024],
        "inputs": [
            (
                "model_3d",
                "FILE_3D_GLB,FILE_3D_GLTF,FILE_3D_FBX,FILE_3D_OBJ,FILE_3D_STL,"
                "FILE_3D_USDZ,FILE_3D",
            )
        ],
        "outputs": [
            ("model_3d", "FILE_3D_ANY"),
            ("model_3d_info", "LOAD3D_MODEL_INFO"),
            ("camera_info", "LOAD3D_CAMERA"),
            ("width", "INT"),
            ("height", "INT"),
        ],
    },
}


def load_pack():
    spec = importlib.util.spec_from_file_location(
        "sloyd_pack", os.path.join(REPO, "__init__.py"), submodule_search_locations=[REPO]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sloyd_pack"] = mod
    spec.loader.exec_module(mod)
    return mod


PACK = load_pack()

# The 3D nodes only report FILE_3D_GLB when comfy_api is importable; otherwise they
# degrade to a plain STRING path (see base.MODEL_3D_TYPE). Generating examples against
# the degraded type would emit workflows that cannot connect to Preview 3D, so require
# ComfyUI on the path.
_model_3d_type = PACK.NODE_CLASS_MAPPINGS["SloydTextTo3D"].RETURN_TYPES[0]
if _model_3d_type != "FILE_3D_GLB":
    sys.exit(
        "ComfyUI is not importable, so model_3d resolves to "
        f"{_model_3d_type!r} instead of 'FILE_3D_GLB'.\n"
        "Re-run with ComfyUI on the path, e.g.:\n"
        "  PYTHONPATH=/path/to/ComfyUI /path/to/ComfyUI/.venv/bin/python "
        "scripts/generate_example_workflows.py"
    )


def sloyd_shape(node_type):
    cls = PACK.NODE_CLASS_MAPPINGS[node_type]
    schema = cls.INPUT_TYPES()
    widgets, inputs = [], []
    for section in ("required", "optional"):
        for name, defn in (schema.get(section) or {}).items():
            t = defn[0]
            meta = defn[1] if len(defn) > 1 and isinstance(defn[1], dict) else {}
            if isinstance(t, list):
                widgets.append((name, meta.get("default", t[0] if t else None)))
            elif t in WIDGET_SCALARS:
                default = meta.get(
                    "default",
                    "" if t == "STRING" else False if t == "BOOLEAN" else 0,
                )
                widgets.append((name, default))
                if meta.get("control_after_generate"):
                    # Always "fixed" in examples: with "randomize" the seed rewrites
                    # itself after each run, so every queue press re-executes and
                    # re-bills every upstream Sloyd node.
                    widgets.append((f"{name}__control", "fixed"))
            else:
                inputs.append((name, t))
    outputs = list(zip(cls.RETURN_NAMES, cls.RETURN_TYPES))
    return widgets, inputs, outputs


class WF:
    def __init__(self):
        self.nodes, self.links = [], []
        self.nid = self.lid = 0

    def add(self, node_type, pos, overrides=None, size=None):
        self.nid += 1
        if node_type in CORE:
            c = CORE[node_type]
            widgets = list(c["widgets"])
            inputs = [{"name": n, "type": t, "link": None} for n, t in c["inputs"]]
            outputs = [
                {"name": n, "type": t, "links": [], "slot_index": i}
                for i, (n, t) in enumerate(c["outputs"])
            ]
        else:
            wdefs, indefs, outdefs = sloyd_shape(node_type)
            ov = overrides or {}
            widgets = [ov.get(name, default) for name, default in wdefs]
            inputs = [{"name": n, "type": t, "link": None} for n, t in indefs]
            outputs = [
                {"name": n, "type": t, "links": [], "slot_index": i}
                for i, (n, t) in enumerate(outdefs)
            ]
        node = {
            "id": self.nid,
            "type": node_type,
            "pos": list(pos),
            "size": list(size or [340, 200]),
            "flags": {},
            "order": self.nid - 1,
            "mode": 0,
            "inputs": inputs,
            "outputs": outputs,
            "properties": {"Node name for S&R": node_type},
            "widgets_values": widgets,
        }
        self.nodes.append(node)
        return node

    def link(self, src, out_name, dst, in_name):
        so = next(i for i, o in enumerate(src["outputs"]) if o["name"] == out_name)
        di = next(i for i, o in enumerate(dst["inputs"]) if o["name"] == in_name)
        self.lid += 1
        src["outputs"][so]["links"].append(self.lid)
        dst["inputs"][di]["link"] = self.lid
        ty = src["outputs"][so]["type"]
        accepted = {x.strip() for x in str(dst["inputs"][di]["type"]).split(",")}
        if ty not in accepted and dst["inputs"][di]["type"] != "*":
            raise SystemExit(
                f"type mismatch: {src['type']}.{out_name} ({ty}) -> "
                f"{dst['type']}.{in_name} accepts {sorted(accepted)}"
            )
        self.links.append([self.lid, src["id"], so, dst["id"], di, ty])

    def dump(self, filename, note):
        wf = {
            "last_node_id": self.nid,
            "last_link_id": self.lid,
            "nodes": self.nodes,
            "links": self.links,
            "groups": [],
            "config": {},
            "extra": {"sloyd_note": note},
            "version": 0.4,
        }
        path = os.path.join(OUT, filename)
        with open(path, "w") as f:
            json.dump(wf, f, indent=2)
            f.write("\n")
        print(f"  {filename:30} {self.nid} nodes, {self.lid} links")


def main():
    os.makedirs(OUT, exist_ok=True)
    print("generating example workflows from the local package...")

    w = WF()
    a = w.add(
        "SloydTextTo3D",
        [40, 40],
        {"prompt": "a medieval knight helmet, game asset", "texture_resolution": "2k"},
        size=[360, 300],
    )
    b = w.add("Preview3DAdvanced", [460, 40], size=[420, 500])
    w.link(a, "model_3d", b, "model_3d")
    w.dump("Sloyd 3D - Text to 3D Model.json", "Generate a 3D model from a text prompt and preview it.")

    w = WF()
    li = w.add("LoadImage", [40, 40], size=[320, 320])
    a = w.add("SloydImageTo3D", [400, 40], {"texture_resolution": "2k"}, size=[340, 260])
    b = w.add("Preview3DAdvanced", [780, 40], size=[420, 500])
    w.link(li, "IMAGE", a, "image")
    w.link(a, "model_3d", b, "model_3d")
    w.dump("Sloyd 3D - Image to 3D Model.json", "Turn a reference image into a 3D model.")

    w = WF()
    a = w.add(
        "SloydTextToSkybox",
        [40, 40],
        {"prompt": "a neon cyberpunk alley at night, rain"},
        size=[360, 260],
    )
    b = w.add("PreviewImage", [460, 40], size=[460, 460])
    w.link(a, "skybox", b, "images")
    w.dump(
        "Sloyd 3D - Text to Skybox 360 Panorama.json",
        "Generate a 360 equirectangular skybox. The saved file is full resolution; "
        "output_max_size only caps the in-graph image so previews stay fast. Swap "
        "Preview Image for a 360 viewer (e.g. ComfyUI_preview360panorama) to look around.",
    )

    w = WF()
    a = w.add(
        "SloydTextTo3D",
        [40, 40],
        {"prompt": "a simple ceramic mug", "texture_resolution": "2k"},
        size=[360, 300],
    )
    p1 = w.add("Preview3DAdvanced", [460, 40], size=[380, 420])
    r = w.add(
        "SloydRetexture",
        [460, 500],
        {"prompt": "weathered bronze with green patina", "texture_resolution": "2k"},
        size=[360, 260],
    )
    p2 = w.add("Preview3DAdvanced", [880, 400], size=[380, 420])
    w.link(a, "model_3d", p1, "model_3d")
    w.link(a, "sloyd_job", r, "sloyd_job")
    w.link(r, "model_3d", p2, "model_3d")
    w.dump(
        "Sloyd 3D - Retexture 3D Model.json",
        "Generate a model, then retexture it. The sloyd_job wire carries the source id, "
        "so leave job_id blank. Keep 'control after generate' on fixed so re-running only "
        "re-bills the node you changed.",
    )

    # Self-check: widget counts must match the current node definitions exactly.
    print("\nvalidating...")
    for fn in sorted(os.listdir(OUT)):
        if not fn.endswith(".json"):
            continue
        wf = json.load(open(os.path.join(OUT, fn)))
        for n in wf["nodes"]:
            if n["type"] in CORE:
                continue
            wdefs, indefs, outdefs = sloyd_shape(n["type"])
            assert len(n["widgets_values"]) == len(wdefs), (
                f"{fn}: {n['type']} has {len(n['widgets_values'])} widget values, "
                f"expected {len(wdefs)} ({[w[0] for w in wdefs]})"
            )
            assert [o["name"] for o in n["outputs"]] == [o[0] for o in outdefs]
            assert "randomize" not in [str(v) for v in n["widgets_values"]], (
                f"{fn}: {n['type']} ships randomize; that re-bills on every run"
            )
        print(f"  OK {fn}")
    print("\nall examples validated against the current node definitions")


if __name__ == "__main__":
    main()
