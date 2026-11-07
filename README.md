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

The normal production schedule is:

```yaml
schedule:
  - cron: '17 0,4 * * *'
```

GitHub cron is in **UTC**: this means **08:17 and 12:17 Taiwan time** every day. GitHub Actions scheduling is best-effort; runs may be delayed or occasionally skipped.

**Temporary schedule trigger test:** To test that GitHub actually starts `schedule` runs, change only the cron line on `main` to:

```yaml
schedule:
  - cron: '*/5 * * * *'
```

This is **temporary**, not the intended normal frequency. After a genuine scheduled run appears in Actions, restore `17 0,4 * * *` and commit again. The validation tests accept either value for this diagnostic purpose.

When viewing the Actions run, distinguish events:

- `schedule`: GitHub triggered the workflow automatically — this is the event the test aims to verify.
- `workflow_dispatch`: a person clicked **Run workflow** — it does not prove scheduling works.
- `push`: a commit triggered validation — it also does not prove scheduling works.

With no changed patch source, an expected successful scheduled run shows **check: success**, **build: skipped**, **publish: skipped**. Check that the workflow is enabled in the Actions UI, especially on a fork. Don't interpret an isolated missing 5-minute tick as definitive failure: GitHub's scheduler does not guarantee exact timing.

### Manual build

Open [Actions → Personal FB IG YouTube Discord](https://github.com/bitstone0117/Mophe-AutoBuilds/actions/workflows/personal-build.yml), click **Run workflow**, use branch `main`, then choose:

- `all`: force a build and publish of all four apps.
- `youtube`, `instagram`, `facebook`, or `discord`: force a build **and publish only that app**.

**Manual builds are forced**, even if the upstream patch release has not changed. Avoid using `all` to test no-change automatic checks; only a real `schedule` run verifies that path.

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
