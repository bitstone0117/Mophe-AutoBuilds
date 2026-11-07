#!/usr/bin/env bash
# Run from release-apks. A failed upload must not replace the published baseline.
set -euo pipefail
for app in youtube instagram facebook; do
  files=("$app"-*.apk)
  [[ ${#files[@]} -eq 1 && -s "${files[0]}" ]]
done
tag="build-${GITHUB_RUN_NUMBER}-${GITHUB_RUN_ATTEMPT}"
gh release create "$tag" *.apk SHA256SUMS.txt obtainium.json source-state.json \
  --draft --target "$GITHUB_SHA" \
  --title "Personal build ${GITHUB_RUN_NUMBER}.${GITHUB_RUN_ATTEMPT}" \
  --notes 'YouTube (Morphe), Instagram (HushGram), Facebook (HushFacebook). All selected builds and APK signature verification passed. Device installation is not yet verified.'
# Only advertise the release after every asset has uploaded successfully.
gh release edit "$tag" --draft=false --latest
