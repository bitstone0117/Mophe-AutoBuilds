# FB / IG / YouTube personal automation

The personal workflow checks stable upstream patch releases at **08:17 Taipei**
(00:17 UTC), with a **12:17 Taipei** catch-up check (04:17 UTC). GitHub schedules
are best-effort and may be delayed or dropped. Both checks compare against
`source-state.json` on the latest published release. No changes means no APK
build and no release; a change to any source builds all three apps.

Comparison includes the release tag and sorted asset names, IDs and digests,
so replacing an asset under the same tag is detected. It intentionally includes
release metadata assets as well as patch bundles. This monitors patch releases,
not standalone CLI releases or every new stock APK version. Missing state or
an incomplete published release triggers recovery builds; API/download errors
fail the check instead of being interpreted as an update.

Manual runs intentionally force a build for troubleshooting. Select `all` to
publish; single-app tests never publish. Any failed/cancelled build blocks
publication. Immediately before publishing, the workflow checks that upstream
still matches the captured state; if it changed during the build, the run fails
and the next check retries. APKs and state upload to a draft first; only a
successful upload is made public/latest. Failed drafts do not advance the
comparison baseline. Remove abandoned drafts manually when convenient.

## Schedule diagnosis and recovery

Observed on 2026-11-07:

- Default branch: `main`; personal workflow ID: `409036289`; API state: `active`.
- Repository created 2026-11-06; 60-day inactivity cannot explain this incident.
- Manual run #11 succeeded (check, all three builds, publish); schedule runs: 0.
- `17 0 * * *` is valid and means 08:17 Taipei. The checker cannot prevent a
  schedule event from being created, since it runs only after that event.
- GitHub does not expose its cron registration/queue state. These observations
  do not prove fork disablement, an actor issue, or a dropped scheduler event.
  The Actions settings endpoint requires authentication/admin access that was
  unavailable through the review connection, so its current policy is unverified.

The cron change retains 08:17 and adds a catch-up check. Merge the PR into `main`
to make the schedule change effective; PR branches do not register schedules.
Changing cron is GitHub's documented way to reactivate a deactivated schedule
and associate its actor with the change. This is a mitigation, not proof of the
original cause or a guarantee of an on-time run.

In **Actions → Personal FB IG YouTube**, click **Enable workflow** if shown.
For a fresh fork, first accept **I understand my workflows, go ahead and enable
them** if shown. In **Settings → Actions → General**, confirm Actions are enabled
and the policy permits the actions used here. Do not broaden an existing policy
unnecessarily. No signing secrets or package names need to change.

With an authenticated GitHub CLI, verify or enable the workflow:

```sh
gh api repos/bitstone0117/Mophe-AutoBuilds/actions/workflows/personal-build.yml --jq .state
gh workflow enable personal-build.yml --repo bitstone0117/Mophe-AutoBuilds
gh run list --repo bitstone0117/Mophe-AutoBuilds --workflow personal-build.yml --event schedule
```

After merge, confirm a real `schedule` run at the next check window. `active`
and a successful manual run alone do not prove the scheduler works. If both
windows are missed while still active, provide the workflow ID and timestamps
to GitHub Support. Avoid unconditional rebuilds or empty daily keepalive commits.

References: [GitHub schedule behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule),
[enable a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows).

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

HushFacebook patches follow the latest stable release, just like Morphe and
HushGram. Stock APK compatibility is handled by the existing source resolvers
and validation. A new patch release that cannot be built safely will fail and
leave the last complete published release/state intact; it must not be marked
as successfully processed. Device installation still requires verification.

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
