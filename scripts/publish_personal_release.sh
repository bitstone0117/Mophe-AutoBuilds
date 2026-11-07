#!/usr/bin/env bash
# Run from release-apks. A failed upload must not replace the published baseline.
set -euo pipefail

# Verify precisely the APKs selected by the checker. No unrelated APKs.
notes="$(python - <<'PY'
import json
from pathlib import Path

state = json.loads(Path("source-state.json").read_text())
selected = state.get("selected_apps")
allowed = {"youtube": "YouTube (Morphe)", "instagram": "Instagram (HushGram)",
           "facebook": "Facebook (HushFacebook Clone)", "discord": "Discord (Venus)"}
if not isinstance(selected, list) or not selected or len(selected) != len(set(selected)):
    raise SystemExit("Expected a nonempty, unique selected_apps list")
if any(app not in allowed for app in selected):
    raise SystemExit("Unknown app selected for release")

apks = list(Path(".").glob("*.apk"))
if len(apks) != len(selected):
    raise SystemExit(f"Expected {len(selected)} APKs for {selected}; got {[p.name for p in apks]}")
for app in selected:
    matches = [p for p in apks if p.name.startswith(f"{app}-") and p.stat().st_size > 0]
    if len(matches) != 1:
        raise SystemExit(f"Missing or duplicate signed APK for {app}")

print("Updated: " + ", ".join(allowed[app] for app in selected) +
      ". Only the listed apps were rebuilt. APK signatures verified; device installation not yet verified.")
PY
)"

tag="build-${GITHUB_RUN_NUMBER}-${GITHUB_RUN_ATTEMPT}"
gh release create "$tag" *.apk SHA256SUMS.txt obtainium.json source-state.json \
  --draft --target "$GITHUB_SHA" \
  --title "Personal build ${GITHUB_RUN_NUMBER}.${GITHUB_RUN_ATTEMPT}" \
  --notes "$notes"
# Advertise the release only after all selected assets upload successfully.
gh release edit "$tag" --draft=false --latest
