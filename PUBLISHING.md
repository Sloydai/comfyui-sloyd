# Publishing to the Comfy Registry

Internal notes for releasing this pack. Users don't need this file.

## One-time setup

**1. Rotate and store the Registry key.**
The publishing key is a credential that lets anyone publish node versions under
`@sloyd`, which ComfyUI-Manager will then install onto users' machines. Treat it like
a deploy key.

- Generate it at https://registry.comfy.org (pick the `sloyd` publisher → API Keys).
- Store it **only** as a GitHub Actions secret named `REGISTRY_ACCESS_TOKEN`
  (Settings → Secrets and variables → Actions on the repo).
- Never commit it, never paste it into chat or an issue.

**2. Add the icon and banner.**
`pyproject.toml` has `Icon` and `Banner` under `[tool.comfy]`, currently blank. These
drive how the pack looks in ComfyUI-Manager and on the Registry listing, so a listing
without them looks unfinished next to competitors.

| Field | Requirements |
| --- | --- |
| `Icon` | square, max 400×400, SVG/PNG/JPG/GIF |
| `Banner` | 21:9 aspect, SVG/PNG/JPG/GIF |

Both must be publicly reachable URLs (e.g. committed to this repo and referenced via
their raw GitHub URL, or hosted on sloyd.ai).

## Template thumbnails (animated, and why they are named .jpg)

The cards in **Workflow → Browse Templates** are driven entirely by two things per
template: the `.json` filename (which *is* the displayed title) and a same-named
image beside it. Verified in the frontend source, `workflowTemplatesStore.ts`
hardcodes both fields for custom-node templates:

```ts
mediaType: 'image',
mediaSubtype: 'jpg',
```

So a real `<video>` thumbnail is impossible, and the frontend will only ever request
`<name>.jpg`. Tags and the crown badge are also unavailable; those belong to
Comfy-Org's curated partner index, which a custom pack cannot write into.

**What we do instead:** the four `.jpg` files are actually **animated WebP**. Browsers
content-sniff images and ignore the extension, so a ~3 s loop plays in the card. This
was verified end to end against the real ComfyUI static route in a headed browser
(4/4 load and animate), with a correctly-named control to prove the test itself works.

Each is a genuine render of that workflow's own output, not stock or AI-generated
footage: turntables come from the actual GLBs, and the skybox loop is a real camera
pan inside the actual equirectangular panorama.

| Card | Loop |
| --- | --- |
| Text to 3D Model | treasure chest turntable |
| Image to 3D Model | static input photo beside the rotating mesh |
| Text to Skybox 360 Panorama | 360° pan from inside the panorama |
| Retexture 3D Model | one mesh, three materials, rotating in lockstep |

Specs: 640×360, 36 frames at 80 ms (~2.9 s), WebP quality 55–62, 242–411 KB each
(~1.2 MB total). GIF was rejected: 1.67 MB for the same loop, with 256-colour banding.

**Known fragility:** this relies on the extension not matching the contents. If
ComfyUI ever validates that a `.jpg` is really JPEG, all four cards would fall back to
the "missing thumbnail" gradient at once. Frame 0 of each loop is composed to stand
alone as a still, which limits the damage but does not prevent it. If that happens,
re-encode the same first frames as real JPEG and lose only the motion.

## Regenerating the example workflows

`example_workflows/*.json` are generated, not hand-edited. A workflow's
`widgets_values` is a positional array, so adding or reordering a single node input
silently shifts every later value (a stale example would read a timeout as an image
size, for instance). After changing any node's inputs, run:

```bash
PYTHONPATH=/path/to/ComfyUI /path/to/ComfyUI/.venv/bin/python \
  scripts/generate_example_workflows.py
```

ComfyUI must be on the path: without it the 3D nodes degrade `model_3d` from
`FILE_3D_GLB` to a plain `STRING`, and the script refuses to emit examples that
could not connect to Preview 3D. It also self-checks widget counts and fails if any
example would ship `control after generate: randomize`.

## Releasing a version

`version` in `pyproject.toml` is the release number and uses semver:

- **patch** (0.1.0 → 0.1.1) bug fixes
- **minor** (0.1.0 → 0.2.0) new nodes or features, backwards compatible
- **major** (0.1.0 → 1.0.0) breaking changes, e.g. renaming a node id or removing an
  output, both of which break users' saved workflows

A published version cannot be withdrawn, only superseded by a higher one. So bump,
verify, then publish.

### Option A — GitHub Actions (recommended)

`.github/workflows/publish.yml` runs whenever `pyproject.toml` changes on `main`.
Bump `version`, merge to `main`, and it publishes. No local tooling, and the key
never leaves GitHub.

### Option B — locally with comfy-cli

```bash
pip install comfy-cli
comfy node publish        # prompts for the API key
```

Run this from the repo root.

## Pre-publish checklist

Everything here has been verified except the last two items, which need a human.

- [x] `LICENSE` present and matching `pyproject.toml`
- [x] Repo URLs point at `Sloydai/comfyui-sloyd`
- [x] `keywords` cover the terms users search (3d, skybox, panorama, hdri, retexture…)
- [x] `sloyd_config.json` is in `.gitignore` **and** `.comfyignore` so no credential
      can ship in the published archive
- [x] All 12 nodes load and register in a real ComfyUI
- [x] Example workflows validated against live node definitions
- [x] Example workflows ship `control after generate: fixed` so users aren't silently
      re-billed on every queue press
- [ ] `Icon` and `Banner` URLs filled in
- [ ] Verified the published listing renders correctly after the first publish

## Known upstream issues to track

These are Sloyd API behaviours the pack works around. Revisit when the API changes.

| Issue | Workaround in the pack |
| --- | --- |
| `/jobs/retexture` with `textureResolution: "auto"` returns a GLB with UVs but no texture images, so the model renders grey. Reproducer: source `su5hqeb6` → job `llu2b460` (auto, 0 textures) vs `b3pppweo` (2k, 3 textures). | `auto` removed from the Retexture node; default is `2k`. |
| Skybox results are not published at `jobs/{id}.glb`; the panorama URL is inside the job response at `flatBoxData.panoramaUrl`. | Skybox nodes read `panoramaUrl`. |
| `sketch-to-image` rejects a JSON body with HTTP 500; it needs a multipart file upload. | Sketch to Image posts multipart. |
| Skyboxes come back 4096×4096 (1:1, not the usual 2:1). As a ComfyUI IMAGE that is a ~201 MB tensor, which makes preview nodes unreliable. | Skybox nodes expose `output_max_size` (default 2048) which caps only the in-graph tensor; the saved file stays full resolution. |
| `multi-image-to-3d` can exceed 600 s. | That node defaults to a 1500 s timeout. |
| Retexturing a job owned by a different Sloyd account returns HTTP 403 "You can't retexture other users' creations". | Not yet surfaced as a friendly error. |
