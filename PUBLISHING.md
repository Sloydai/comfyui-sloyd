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
| Skyboxes come back 4096×4096 (1:1, not the usual 2:1). As a ComfyUI IMAGE that is a ~201 MB tensor, which makes preview nodes unreliable. | Not yet addressed; an `output_max_size` option is the proposed fix. |
| `multi-image-to-3d` can exceed 600 s. | That node defaults to a 1500 s timeout. |
| Retexturing a job owned by a different Sloyd account returns HTTP 403 "You can't retexture other users' creations". | Not yet surfaced as a friendly error. |
