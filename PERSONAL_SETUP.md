# FB / IG / YouTube personal automation

Status: prepared for a personal fork; no device or cloud build has been verified yet.

Only `personal-build.yml` is active. It builds all three apps daily at 08:17
Asia/Taipei (GitHub may delay runs) or through Run workflow. A failed matrix
build prevents the whole release. Every complete build gets a new release tag,
so patch-only changes are visible to Obtainium. This deliberately trades extra
daily builds for straightforward update detection.

## Private signing setup

Export the existing signing key from Morphe Manager. Do not commit or upload it
to chat. In your fork, Settings → Secrets and variables → Actions, configure:

| Secret | Value |
|---|---|
| KEYSTORE_BASE64 | Base64 encoding of the exported signing key |
| KEYSTORE_PASSWORD | The actual keystore password |
| KEY_PASSWORD | The actual private-key password |
| KEY_ALIAS | The actual key alias |

Determine the alias using `keytool -list -keystore Morphe.p12` locally; it prompts
for the password. Do not guess the alias or password. This workflow uses the
same key for all three apps. If existing apps use different signing keys,
configure per-app signing before the first build. The inherited public key is
never used by the personal workflow.

Confirm existing package names and patch selections, especially clone mode and
Disable Play Store updates, before installing. Current defaults use Hush's
recommended patches. Matching signing keys alone is insufficient if the package
name or versionCode is incompatible. Do not uninstall to work around an update
error if preserving local data is required.

## Facebook compatibility

HushFacebook is pinned to v0.21.0 and Facebook 585.0.0.47.54, arm64 build
476015655. The downloaded original bundle must match the upstream SHA-256
1090dff6c9fe4903dd7c590f4d340bf0a912e43cd0a79c019c43bc265f5dda53.
A changed bundle fails closed. Updating Facebook compatibility requires changing
the patch tag, version, build and hash together after upstream verification.
Facebook patch updates are therefore intentionally not yet fully automatic.

## First run

1. Create your fork, enable Actions, and add the four secrets.
2. Run **Personal FB IG YouTube** manually and inspect all three build jobs.
3. Download `obtainium.json` from the successful release and import it into
   Obtainium. If the installed Obtainium version requires a full exported app
   record, add the repository URL manually three times using these APK filters:
   `^facebook-.*\.apk$`, `^instagram-.*\.apk$`, `^youtube-.*\.apk$`.
4. Let Obtainium use the GitHub release tag as the version. Enable its option to
   ignore APK version detection for this source if required; the APK versionName
   is not the build tag. Confirm patch-only reinstall works on your phone.
5. Manually verify one update for each app, then enable background updates.

No public Pages site, Telegram messaging, or automatic old-run deletion is
enabled. Historical releases accumulate; periodically remove obsolete APK
releases if desired. Obtainium import and Android silent installation still
require device validation. Public APK releases are visible to everyone.
