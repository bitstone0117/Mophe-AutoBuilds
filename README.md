# Personal APK AutoBuilds — YouTube / Instagram / Facebook / Discord

> A personal fork of [yashrajrocxx/Mophe-AutoBuilds](https://github.com/yashrajrocxx/Mophe-AutoBuilds). This README describes **this fork's configuration**, not the upstream app catalog or upstream download links.

This repository uses GitHub Actions to check community patch releases, build selected patched Android APKs, sign them with the configured private key, and publish them to [this fork's Releases](https://github.com/bitstone0117/Mophe-AutoBuilds/releases). It only builds the apps whose monitored patch source has changed; a manual run can force a particular app.

**Links:** [Personal build workflow](.github/workflows/personal-build.yml) · [Actions / run history](https://github.com/bitstone0117/Mophe-AutoBuilds/actions/workflows/personal-build.yml) · [Latest Release](https://github.com/bitstone0117/Mophe-AutoBuilds/releases/latest) · [Setup / troubleshooting notes](PERSONAL_SETUP.md) (some historical notes there describe earlier versions of this fork).

## Supported apps

| App | Patch source | Android package ID in the generated APK | Architecture |
| --- | --- | --- | --- |
| YouTube (Morphe) | [Morphe patches](https://github.com/MorpheApp/morphe-patches) | `app.morphe.android.youtube` | `universal` |
| Instagram (HushGram) | [HushGram](https://github.com/SysAdminDoc/HushGram) | `com.instagram.android` | `arm64-v8a` |
| Facebook (HushFacebook + Morphe Clone app) | [HushFacebook](https://github.com/SysAdminDoc/HushFacebook), plus Morphe clone patch | `com.facebook.katana.morphe` | `arm64-v8a` |
| Discord (Venus) | [Venus Patches](https://github.com/VenusIsJaded/Venus-Patches) | `com.discord` | `arm64-v8a` |

**Facebook is a clone:** Its package ID differs from stock Facebook's `com.facebook.katana`, so it can coexist with a Samsung/preinstalled Facebook app. Instagram and Discord retain their normal package IDs; modified signatures can conflict with already installed official apps. Do not uninstall an existing app merely to fix a signature conflict if you need to preserve its data. The same signing key should be retained across future builds.

## How automatic updates work

The workflow is [`.github/workflows/personal-build.yml`](.github/workflows/personal-build.yml).

1. **Check:** `scripts/check_personal_updates.py` queries the latest patch Release for each of the four upstream sources. It compares release tags and patch Release asset metadata with the cumulative `source-state.json` stored in the **latest completed Release in this fork**.
2. **Select:** If nothing changed, `check` succeeds and `build` / `publish` are skipped. If one or more monitored sources changed, the workflow selects **only those apps**.
3. **Build and verify:** The selected APKs are downloaded, patched, signed, and checked. A failed build prevents publication.
4. **Publish:** A draft Release is created with only the selected APK(s), `SHA256SUMS.txt`, `source-state.json`, and `obtainium.json`. The Release becomes public/latest only after all selected files upload successfully. Unselected apps keep their previous source-state baselines.

The checker tracks upstream **patch releases**, not all Play Store APK releases or every possible tool update. Failures in upstream/API requests do not count as successful checks.

A single-app Release is intentional: for example, if only Discord changes, that Release has the Discord APK and **does not re-upload** the unchanged YouTube, Instagram, or Facebook APKs.

### Scheduled checks (Taiwan / Asia-Taipei)

GitHub's native `schedule` trigger has been **removed** from `.github/workflows/personal-build.yml`, because it did not produce scheduled runs in this fork. The workflow now starts only through `workflow_dispatch` (manual GitHub Actions runs or an external API caller).

An external cron-job.org task has been successfully tested triggering `app=check`; the intended ongoing cadence is **daily at 00:00 Asia/Taipei**, configured in the cron-job.org account rather than this repository. Verify and save the schedule there; changes in this GitHub repository cannot configure or confirm the external task's timetable.

For a successful run with unchanged upstream patches, expect **check: success**, **build: skipped**, and **publish: skipped**.

### Manual build

Open [Actions → Personal FB IG YouTube Discord](https://github.com/bitstone0117/Mophe-AutoBuilds/actions/workflows/personal-build.yml), click **Run workflow**, use branch `main`, then choose:

- `all`: force a build and publish of all four apps.
- `check`: perform the normal **selective update check** (build/publish only changed patch sources; skip if none changed). This is suitable for external scheduled `workflow_dispatch` calls.
- `youtube`, `instagram`, `facebook`, or `discord`: force a build **and publish only that app**.

Manual `all` and single-app selections are forced, even if the upstream patch release has not changed. The `check` selection is **not** forced; it uses the same selective-update behavior for manual or external scheduled dispatch.


### External scheduled dispatch (cron-job.org)

If the repository's Actions history shows **zero `schedule` events**, even while enabled and on `main`, the problem occurs before the checker job runs. GitHub's own scheduler cannot be repaired from inside `check_personal_updates.py`. GitHub's public-fork and scheduling behavior is described in the [GitHub documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

This fork uses an externally managed scheduler ([cron-job.org](https://cron-job.org/en/)) to send a `POST` to GitHub's [workflow dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event). Keep the external task enabled and configured with:

```text
POST https://api.github.com/repos/bitstone0117/Mophe-AutoBuilds/actions/workflows/personal-build.yml/dispatches
Authorization: Bearer <fine-grained PAT>
Accept: application/vnd.github+json
Content-Type: application/json
```

Body:

```json
{"ref":"main","inputs":{"app":"check"}}
```

Create the fine-grained PAT for **only this repository**, granting only **Actions: Read and write** (required by the dispatch API). It is **not** the read-only GitHub PAT used by Obtainium. Treat this PAT as a privileged secret: an external scheduler would hold it, so use a trustworthy service, a limited expiration, and revoke it if no longer needed. Do not put the token in code, Release assets, README, support tickets, or chat.

Configure the external scheduler for **00:00 Asia/Taipei daily** (UTC 16:00 on the previous calendar day) and verify its timezone setting. A successful API request returns HTTP 204 and creates a **`workflow_dispatch`** run. The `check` input is essential: omitting it would use the `all` default and force four rebuilds on each call. External scheduling is configured and managed in cron-job.org, **not** through this repository.

## Install and update with Obtainium

Download `obtainium.json` from [this fork's latest Release](https://github.com/bitstone0117/Mophe-AutoBuilds/releases/latest), then import it into [Obtainium](https://github.com/ImranR98/Obtainium). Back up your existing Obtainium settings before replacing or importing app entries.

The generated configuration tracks this repository, applies a separate APK filename filter for each app, and includes:

```json
{
  "fallbackToOlderReleases": true,
  "versionDetection": false
}
```

- **Fallback to older releases** (繁中：**退回使用較舊的版本**) allows each app to find its newest APK even when the *latest* repository Release only contains a different app.
- **Version detection disabled** avoids treating the Android APK `versionName` as equivalent to GitHub Release tags such as `build-15-1` and `build-16-1`.

Each app must follow **the newest Release that actually contains its matching APK**, not necessarily the repository's overall latest Release. For example, after a Discord-only Release, Discord may track `build-16-1` while the other three still track `build-15-1`.

**Important:** Importing settings can initially show `未知` or offer updates for already-installed APKs until GitHub checks complete and Obtainium reconciles its locally tracked installation state. A displayed update button does not prove that APK has changed. Verify the installed APK matches the published build before choosing **標記為已更新**; that action only changes Obtainium's tracking record and does **not** install the APK.

**GitHub rate limits:** If Obtainium reports too many requests, wait for the retry period or configure a GitHub personal access token inside **Obtainium → 設定 → 特定來源 → GitHub 個人存取權杖（可提高速率限制）**. Use a token with minimal read-only public-repository access; never publish or paste it into an issue, README, or chat.

## GitHub Actions secrets and signing

Configure the following in **Settings → Secrets and variables → Actions** on your own fork before building:

| Secret | Purpose |
| --- | --- |
| `KEYSTORE_BASE64` | Base64-encoded private signing keystore |
| `KEYSTORE_PASSWORD` | Keystore password |
| `KEY_PASSWORD` | Key password |
| `KEY_ALIAS` | Signing alias |
| `GPLAYDL_API_KEY` | Google Play download access required for the Instagram build in this workflow |

Signing material belongs only in GitHub Actions secrets; never commit the keystore or credential values. Existing installs need matching package IDs and signing certificates for in-place updates. The workflow can verify build artifacts and signatures, but on-device installation, logins, and compatibility must still be tested separately.

## Project files

- `patch-config.json`: selected apps and patch sources
- `arch-config.json`: architecture per app
- `sources/` and `patches/`: upstream definitions and patch options
- `scripts/check_personal_updates.py`: per-app change detection and published baseline tracking
- `scripts/personal_obtainium.py`: generated Obtainium import settings
- `scripts/publish_personal_release.sh`: selective Release publishing
- `tests/test_personal_updates.py`: workflow, change-detection, and release-contract tests

## Credits and disclaimer

Forked from [yashrajrocxx/Mophe-AutoBuilds](https://github.com/yashrajrocxx/Mophe-AutoBuilds). Credits belong to the upstream maintainers and respective patch authors. This personal fork is not an official release of YouTube, Meta, Discord, Morphe, HushGram, HushFacebook, or Venus. Use patched APKs at your own risk and only from sources you trust. For the upstream's full original feature catalog and documentation, visit the upstream repository; its Release links and update schedule are **not** this fork's.
