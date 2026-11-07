"""Check patch releases and select only apps needing a new personal build."""
import argparse
import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = "https://api.github.com"
REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ.get("GITHUB_TOKEN", "")

BUILD_PROFILE = "facebook-clone-discord-v1"
SOURCES = {
    "youtube": ("MorpheApp", "morphe-patches"),
    "instagram": ("SysAdminDoc", "HushGram"),
    "facebook": ("SysAdminDoc", "HushFacebook"),
    "discord": ("VenusIsJaded", "Venus-Patches"),
}
BUILD_SOURCES = {
    "youtube": "morphe",
    "instagram": "hushgram",
    "facebook": "hushfacebook",
    "discord": "venus",
}


def fetch_json(url, authenticated=True):
    headers = {
        "User-Agent": "personal-update-checker",
        "Accept": "application/vnd.github+json",
    }
    if authenticated and TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


def source_signature(owner, name):
    release = fetch_json(f"{API}/repos/{owner}/{name}/releases/latest")
    assets = sorted(
        [
            {
                "name": item["name"],
                "id": item["id"],
                "digest": item.get("digest") or "",
            }
            for item in release.get("assets", [])
        ],
        key=lambda item: item["name"],
    )
    if not any(item["name"].endswith(".mpp") for item in assets):
        raise RuntimeError(f"No patch bundle in release: {owner}/{name}")
    return {"tag": release["tag_name"], "assets": assets}


def current_sources():
    return {
        app: source_signature(owner, name)
        for app, (owner, name) in SOURCES.items()
    }


def verify_state(path):
    """Verify only the apps about to be published, not unrelated upstreams."""
    state = json.loads(Path(path).read_text())
    selected = state.get("selected_apps")
    if not isinstance(selected, list) or not selected:
        raise RuntimeError("Missing selected apps; refusing to publish")
    if len(selected) != len(set(selected)) or any(app not in SOURCES for app in selected):
        raise RuntimeError("Invalid selected apps; refusing to publish")
    if state.get("build_profile") != BUILD_PROFILE:
        raise RuntimeError("Build profile mismatch; refusing to publish")
    for app in selected:
        if state.get("sources", {}).get(app) != source_signature(*SOURCES[app]):
            raise RuntimeError(
                f"Patch sources changed during build for {app}; refusing to publish stale state. Retry the workflow."
            )


def load_baseline():
    """Read last completed release's cumulative state, migrating old all-app releases."""
    try:
        release = fetch_json(f"{API}/repos/{REPO}/releases/latest")
    except HTTPError as exc:
        if exc.code != 404:
            raise
        return {}, {}, set()

    assets = release.get("assets", [])
    state_asset = next(
        (item for item in assets if item["name"] == "source-state.json"),
        None,
    )
    state = fetch_json(state_asset["browser_download_url"], authenticated=False) if state_asset else {}
    saved_sources = state.get("sources") or {}
    if not isinstance(saved_sources, dict):
        raise RuntimeError("Invalid saved source state")
    saved_sources = {app: saved_sources[app] for app in SOURCES if app in saved_sources}

    # Older releases had one global profile and required all APKs in one release.
    profiles = state.get("profiles")
    if not isinstance(profiles, dict):
        legacy_profile = state.get("build_profile")
        # The known three-app Facebook-clone build is unchanged by adding Discord.
        if legacy_profile == "facebook-clone-v1":
            legacy_profile = BUILD_PROFILE
        profiles = {app: legacy_profile for app in saved_sources}
    profiles = {app: profiles.get(app) for app in SOURCES if app in saved_sources}

    published = state.get("published_apps")
    if isinstance(published, list):
        published = set(published) & set(SOURCES)
    else:
        # One-time migration: infer pre-selective releases from their APK assets.
        filenames = [item["name"] for item in assets]
        published = {
            app for app in SOURCES
            if any(name.startswith(f"{app}-") and name.endswith(".apk") for name in filenames)
        }
    return saved_sources, profiles, published


def main():
    current = current_sources()
    saved_sources, profiles, published = load_baseline()
    changed = [
        app for app in SOURCES
        if app not in published
        or saved_sources.get(app) != current[app]
        or profiles.get(app) != BUILD_PROFILE
    ]

    choice = os.environ.get("BUILD_SELECTION", "").strip()
    if choice == "all":
        selected = list(SOURCES)
    elif choice in SOURCES:
        selected = [choice]
    elif not choice:
        selected = changed
    else:
        raise RuntimeError(f"Invalid BUILD_SELECTION: {choice}")

    # Update the published baseline ONLY for apps that will actually be built.
    # An unrelated pending update must not be silently marked as completed.
    next_sources = dict(saved_sources)
    next_profiles = dict(profiles)
    for app in selected:
        next_sources[app] = current[app]
        next_profiles[app] = BUILD_PROFILE

    state = {
        "sources": next_sources,
        "profiles": next_profiles,
        "published_apps": [app for app in SOURCES if app in published or app in selected],
        "build_profile": BUILD_PROFILE,
        "selected_apps": selected,
    }
    encoded = base64.b64encode(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    ).decode()
    matrix = {"include": [
        {"app": app, "source": BUILD_SOURCES[app]} for app in selected
    ]}

    print("Changed patch sources:", changed or "none")
    print("Selected apps to build and publish:", selected or "none")

    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(f"has_updates={'true' if selected else 'false'}\n")
        output.write(f"state_b64={encoded}\n")
        output.write(f"selected_apps={json.dumps(selected, separators=(',', ':'))}\n")
        output.write(f"matrix_json={json.dumps(matrix, separators=(',', ':'))}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-state", help="Abort publishing if selected upstream patches changed during build")
    args = parser.parse_args()
    if args.verify_state:
        verify_state(args.verify_state)
    else:
        main()
