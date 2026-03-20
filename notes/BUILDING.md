# Windows Build

This project uses Panda3D's `build_apps` flow to create a portable Windows build for testers.

## Prerequisites

- `ppython` available on `PATH`
- Panda3D installed into that interpreter

## Build

From the repo root:

```powershell
ppython setup.py build_apps
```

Or use the helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_windows.ps1
```

To force a clean rebuild:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_windows.ps1 -Clean
```

## Output

The portable tester build is written under:

```text
build\win_amd64\
```

Send that folder as a zip to testers.

## Release Asset

To build a GitHub release asset zip from the portable Windows build:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\package_release.ps1 -Version v0.1.0
```

This produces a zip under:

```text
dist\
```

Recommended asset name format:

```text
arpg-prototype-win64-v0.1.0.zip
```

## Included Data

The build includes only the static game data needed at runtime:

- `data/creatures.json`
- `data/items.json`
- `data/recipes.json`
- `data/vendors.json`

It intentionally excludes dev/runtime state such as:

- `data/save.json`
- `data/overworld_level.json`
- `runtime/`
- `__pycache__/`

## Tester Notes

- First launch will create runtime save/cache data locally as needed.
- This flow is designed for a portable extracted folder, not an installer.
- If you want an installer later, the runtime save/cache location should move out of the app folder and into a per-user writable directory.

## GitHub Release Flow

1. Commit the packaging files and push your branch.
2. Build the Windows export.
3. Package the release zip.
4. Create a Git tag such as `v0.1.0`.
5. Create a GitHub release for that tag.
6. Upload the generated zip from `dist\`.

If you do not use GitHub CLI, create the release in the GitHub web UI and upload the zip as a release asset.
