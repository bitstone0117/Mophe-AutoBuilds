"""Check patch releases before rebuilding personal APKs."""
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

SOURCES = {
    "youtube": ("MorpheApp", "morphe-patches"),
    "instagram": ("SysAdminDoc", "HushGram"),
    "facebook": ("SysAdminDoc", "HushFacebook"),
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
    release = fetch_json(
        f"{API}/repos/{owner}/{name}/releases/latest"
    )

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

    return {
        "tag": release["tag_name"],
        "assets": assets,
    }


def current_sources():
    return {
        app: source_signature(owner, name)
        for app, (owner, name) in SOURCES.items()
    }


def verify_state(path):
    expected = json.loads(Path(path).read_text())["sources"]
    if expected != current_sources():
        raise RuntimeError("Patch sources changed during build; refusing to publish stale state. Retry the workflow.")


def main():
    current = current_sources()
    try:
        previous_release = fetch_json(
            f"{API}/repos/{REPO}/releases/latest"
        )
    except HTTPError as exc:
        if exc.code != 404:
            raise
        previous_release = None

    old_state = None
    complete_release = False

    if previous_release:
        assets = previous_release.get("assets", [])
        filenames = {item["name"] for item in assets}

        complete_release = all(
            any(
                name.startswith(f"{app}-")
                and name.endswith(".apk")
                for name in filenames
            )
            for app in SOURCES
        )

        state_asset = next(
            (
                item for item in assets
                if item["name"] == "source-state.json"
            ),
            None,
        )

        if state_asset:
            old_state = fetch_json(
                state_asset["browser_download_url"],
                authenticated=False,
            ).get("sources")

    if old_state is None or not complete_release:
        changed = list(SOURCES)
    else:
        changed = [
            app for app in SOURCES
            if old_state.get(app) != current[app]
        ]

    state = json.dumps(
        {"sources": current},
        sort_keys=True,
        separators=(",", ":"),
    )
    encoded = base64.b64encode(state.encode()).decode()

    print("Changed patch sources:", changed or "none")
    print("Build required:", bool(changed))

    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(
            f"has_updates={'true' if changed else 'false'}\n"
        )
        output.write(f"state_b64={encoded}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-state", help="Abort publishing if upstream changed during build")
    args = parser.parse_args()
    if args.verify_state:
        verify_state(args.verify_state)
    else:
        main()
