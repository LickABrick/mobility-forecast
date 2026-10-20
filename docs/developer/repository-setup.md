# Maintainer-only repository setup

These are instructions, not settings changed by this implementation. Current local
branch is `master`; workflows support both `master` and `main`. Apply protections to
the actual default branch. Rename only deliberately, updating default-branch help URLs.

## Actions and release credentials

1. Settings → Actions → General: allow the workflow actions used here. Set default
   workflow token permissions to **Read repository contents**.
2. Enable **Allow GitHub Actions to create and approve pull requests** where available.
3. Create a repository-scoped fine-grained bot PAT with Contents, Pull requests and
   Issues **read/write**, Metadata read. Limit it to this repository, set expiry and
   rotation ownership. Save as Actions secret `RELEASE_PLEASE_TOKEN`. This avoids
   GITHUB_TOKEN's PR-event suppression; verify Quality runs on a generated release PR.
   A GitHub App token is preferred long-term but requires an explicit generation step.
4. Settings → Environments → New environment `release`: require @LickABrick as reviewer,
   restrict deployment branches to the default branch. For a sole maintainer allow
   self-review (do not enable prevent-self-review). Disable admin bypass if practical.
   Check your plan supports environment protection; otherwise dispatch permission is
   the weaker manual gate and must be accepted explicitly before publishing.
5. Publication uses job-scoped GITHUB_TOKEN writes; no secret is required there.
   Never enable auto-merge for release PRs or expose release secrets to fork workflows.

## Branch rules

Settings → Rules → Rulesets → New branch ruleset for default branch:
require pull requests, block force pushes/deletion, require current checks **tests**,
**hassfest**, **hacs** from Quality. Confirm actual displayed contexts after first CI
run before saving; reusable workflow contexts may include a caller prefix. Require
checks on release PRs as well. Require branch up to date if practical.

For a single maintainer do not require an independent approving reviewer or code-owner
approval that the author cannot provide. Codeowners routes review, not a second person.
Require conversation resolution; minimize bypass permissions. Avoid a rule deadlock
where a GITHUB_TOKEN-created PR cannot acquire checks: preparation uses the scoped token.

## Security and dependency updates

Settings → Code security: enable private vulnerability reporting, Dependabot alerts
and security updates. Dependabot version updates are configured weekly in source;
no automatic merge. Review HA/fixture compatibility together. HA minor/major upgrades
are deliberately excluded from automatic update PRs until the supported target is
reviewed. Tooling minor/patch updates are grouped; major changes stay separate.

## First release and HACS

Review [release bootstrap](release-process.md#bootstrap), complete staging, merge the
prepared release PR only after CI, then dispatch publication and approve `release`.
Check all versions/tag/changelog match. Remove the one-time release-as pin afterwards.
HACS uses GitHub Releases when available, otherwise default branch. Custom repository
installation does not establish default catalog acceptance.

Before a later catalog submission verify current [HACS admission requirements](https://www.hacs.xyz/docs/publish/include/):
public GitHub repository, one integration under custom_components, valid manifest and
hacs.json, README/license, local brand/icon.png, passing HACS/Hassfest and useful
published release. Check all current checklist items on the submission date, including
repository metadata and supported download behavior. Do not claim acceptance or submit
automatically. Local branding is supported by current HACS; the old brands ignore is
removed. Hosted HACS validation still needs its normal GitHub API credentials.
