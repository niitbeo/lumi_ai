# Lumi Portrait standalone scope

This directory is the only implementation scope for Lumi Portrait.

- Do not edit `../cubeo_app` or `../portrait_beauty_lab` when working on this application.
- Frontend, FastAPI, models, Kumo materials, thumbnails, presets and tests must remain self-contained below this directory.
- Do not add runtime imports, symlinks or absolute paths that point to another local project.
- Keep the standalone development ports at web `4417` and API `8417` unless the user explicitly requests a change.
- Run `pnpm build`, `node --test tests/rendered-html.test.mjs`, and check `/api/health` before handing off changes.
- Record material architecture or runtime changes in `STANDALONE.md` or `README.md`.
