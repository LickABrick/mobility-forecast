# Maintainer-only repository setup

GitHub's verified default branch is **main**. These are external administrator steps;
no settings, secrets, tags or releases were created by this implementation. Source
contains event guards, validation and templates, not proof that protections are enabled.

## Before release preparation: fine-grained token

1. Personal GitHub avatar → **Settings → Developer settings → Personal access tokens
   → Fine-grained tokens → Generate new token**.
2. Give it a release-preparation name, choose an appropriate short expiration and record
   rotation ownership. Resource owner: **LickABrick**. Repository access: **Only select
   repositories → mobility-forecast**. Do not choose all repositories.
3. Repository permissions: **Contents: Read and write**, **Pull requests: Read and write**,
   **Issues: Read and write**; Metadata read is implicit. No administration or workflow
   write permission is required. Approve organization authorization if applicable.
4. Generate and copy once. Repository → **Settings → Secrets and variables → Actions
   → New repository secret**, name **RELEASE_PLEASE_TOKEN**, paste value and save.
   Never commit, post, log or send the value in an issue. Rotate before expiry.
5. A missing/expired/insufficient token must fail preparation, not silently authenticate
   with a different identity. After main Quality succeeds, verify a release PR appears
   and normal PR Quality runs. To retry a failed setup, rerun the failed Release run
   for the current validated SHA (or rerun Quality's main push run). Outdated runs skip.

A GitHub App token is a future alternative (short-lived tokens, more setup), but the
current workflow expects a fine-grained PAT. Do not configure a nonexistent App secret.

## Actions permissions

Repository → **Settings → Actions → General**: allow the actions used in source.
Under Workflow permissions select read-only repository access by default. Publication
requests explicit job-scoped writes. If GitHub policy requires it, enable **Allow GitHub
Actions to create and approve pull requests**; preparation authenticates as the PAT
owner, not GITHUB_TOKEN. Never enable auto-merge for releases or expose the PAT in PR CI.

## Before publication: protected environment

1. Repository → **Settings → Environments → New environment**, name **release**.
2. Deployment branches/tags: selected branches, allow **main** only.
3. Add @LickABrick as required reviewer if supported by the repository plan. Leave
   **Prevent self-review** off for this single-maintainer process; otherwise the
   dispatcher cannot approve their own deployment. Do not require a second nonexistent
   reviewer. Restrict administrative bypass if practical.
4. After dispatch, Actions → Release run → **Review deployments → release → Approve
   and deploy**. Review SHA/version and passing Quality first.

These rules are not guaranteed by `environment: release` alone. If reviewers are not
available on the plan, explicitly accept workflow-dispatch as the sole manual approval
and restrict repository write access. Do not advertise protected approval in that case.

## Main branch rules

Repository → **Settings → Rules → Rulesets → New branch ruleset**:
name it Main protection, enable enforcement, target branch **main**. Require a PR,
block deletion and force pushes, require Quality contexts **tests**, **hassfest**,
**hacs** (select their exact observed names after the first hosted run), require
conversation resolution and current checks where practical. Do not require a second
approving review or code-owner approval that deadlocks a sole maintainer's own PRs.
CODEOWNERS routes review; it does not invent another reviewer. Keep bypass minimal.
Do not allow ordinary merges while preparing/approving/publishing a release.

## First release checklist

1. Pass hosted Quality/Hassfest/HACS and complete [real staging](staging-validation.md).
2. Wait for the release PR after successful main push Quality. Expected title:
   `chore(main): release 1.0.0`; branch `release-please--branches--main`; label
   `autorelease: pending`. After its final automatic update, finalize **both** body
   and CHANGELOG using [first-release notes](first-release-notes.md). Remove the
   1.0.0-to-itself comparison link. Another preparation run can overwrite these edits;
   freeze merges, recheck both copies and wait for all three checks after editing.
3. Check version.txt, manifest.json, pyproject.toml, const.py and release manifest all
   say 1.0.0 (some may be unchanged in a same-version bootstrap). Confirm runtime marker,
   correct new changelog heading and passing PR checks. Do not modify lifecycle labels.
4. Merge the release PR with normal merge/squash/rebase. Freeze ordinary merges until
   publication. Wait for main Quality; preparation must not publish anything.
5. Actions → **Release → Run workflow**, choose **main**, enable **publish**, run.
   Verify full Quality and approve environment deployment where configured.
6. Verify GitHub Releases contains full release **v1.0.0**, its tag points to the
   validated release-PR commit and archive manifest matches. Check HACS offers and
   installs that version on staging. Source ZIP contains local brand assets.
7. Remove one-time `release-as` (optionally bootstrap-sha) in a maintenance PR before
   the next release. Future fix/feature Conventional Commits select patch/minor versions.

No first release was published during implementation. Read [release semantics and
fixture evidence](release-process.md) before proceeding.

## Maintenance and HACS

Settings → Code security: enable private vulnerability reporting, Dependabot alerts
and security updates. Weekly Dependabot version updates are source-configured; review
PRs through CI. HA minor/major updates require deliberate support review. Hotfixes use
the ordinary tested PR → release PR → dispatch process, never manual retagging.

HACS uses GitHub Releases when present; otherwise it follows the default branch. Custom
repository installation is distinct from default catalog acceptance. Before a later
submission review current [HACS requirements](https://www.hacs.xyz/docs/publish/include/),
metadata, local brand/icon.png, license/docs and passing validators. No submission or
acceptance is claimed. The local validator may need GITHUB_TOKEN to query GitHub.
