"""Generate Obtainium import settings for personal builds."""
import json
import os
from pathlib import Path

repo = os.environ["GITHUB_REPOSITORY"]

package_ids = {
    "facebook": "com.facebook.katana",
    "instagram": "com.instagram.android",
    "youtube": "app.morphe.android.youtube",
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
        }),
    })

Path("release-apks/obtainium.json").write_text(
    json.dumps({"apps": apps, "settings": None}, indent=2)
)
