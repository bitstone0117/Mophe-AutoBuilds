"""Generate Obtainium import settings for selectively published personal builds."""
import json
import os
from pathlib import Path

repo = os.environ["GITHUB_REPOSITORY"]

package_ids = {
    "facebook": "com.facebook.katana.morphe",
    "instagram": "com.instagram.android",
    "youtube": "app.morphe.android.youtube",
    "discord": "com.discord",
}

apps = []
for name, package_id in package_ids.items():
    apps.append({
        "id": package_id,
        "url": f"https://github.com/{repo}",
        "name": name.title(),
        "author": repo.split("/")[0],
        "additionalSettings": json.dumps({
            "apkFilterRegEx": rf"^{name}-.*\.apk$",
            # A release may contain just one updated app. Search older
            # releases for the latest APK of each other app.
            "fallbackToOlderReleases": True,
            # GitHub release tags (build-N-N) differ from APK versionNames.
            "versionDetection": False,
        }),
    })

Path("release-apks/obtainium.json").write_text(
    json.dumps({"apps": apps, "settings": None}, indent=2)
)
