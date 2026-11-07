
#!/usr/bin/env bash
# Run from release-apks.
# A failed upload must not replace the published baseline.
set -euo pipefail

# Require exactly one non-empty APK for every app.
for app in youtube instagram facebook discord; do
  files=("$app"-*.apk)
  [[ ${#files[@]} -eq 1 && -s "${files[0]}" ]]
done

# Create a unique tag for each workflow run.
tag="build-${GITHUB_RUN_NUMBER}-${GITHUB_RUN_ATTEMPT}"

# Upload all APKs and Obtainium metadata as a draft release.
gh release create "$tag" *.apk SHA256SUMS.txt obtainium.json source-state.json \
  --draft --target "$GITHUB_SHA" \
  --title "Personal build ${GITHUB_RUN_NUMBER}.${GITHUB_RUN_ATTEMPT}" \
  --notes 'YouTube (Morphe), Instagram (HushGram), Facebook (HushFacebook Clone), Discord (Venus). All four APK builds and signature verification passed. Device installation is not yet verified.'
# Only publish after every asset uploads successfully.
gh release edit "$tag" --draft=false --latest
