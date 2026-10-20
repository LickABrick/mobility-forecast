# Controlled releases

Release Please v4 uses Conventional Commits and one root component. `version.txt`
is canonical, with atomic Release Please updaters for manifest JSON, project TOML,
runtime constant and release manifest. CI rejects drift. Runtime never parses TOML.
Changelog and `vX.Y.Z` tags describe the exact release. HACS reads GitHub Releases;
without them custom repositories follow the default branch, which is not a safe
release-candidate channel. Back up before installing branch snapshots.

## Bootstrap

Existing 1.0.0 was declared but not published. The configuration deliberately pins
`release-as: 1.0.0` for the first release, with audited baseline SHA as bootstrap.
No tag is created by installing these files. Review the first generated release PR,
including a human-written summary of pre-bootstrap functionality and limitations.
Do not claim all older changes appear automatically in generated notes. After the
first release, remove `release-as` in a maintenance PR so SemVer resumes normally.

## Preparation and approval

1. Configure [repository permissions and environment](repository-setup.md).
2. Merge normal tested Conventional Commit PRs to the default branch. Push invokes
   full reusable Quality checks before Release Please prepares/updates a release PR.
3. Review all version files, changelog, compatibility notes and staging results.
   Required CI must run on the release PR. Merge is a deliberate maintainer decision.
4. Run **Release → Run workflow** on the default branch, set `publish` true.
5. Full Quality (tests, Hassfest, HACS) must pass, then the protected `release`
   environment requires maintainer approval. Tag/changelog checks and branch-movement
   detection run before Release Please creates the tag and full GitHub Release.
6. Verify the resulting tag's manifest, release notes and HACS download. Publication
   uses GITHUB_TOKEN; downstream release/tag event workflows will not automatically run.
   Validation therefore occurs before publication in the same workflow.

Do not merge additional changes while approving publication. Release Please finds
pending merged release PRs; review there is exactly one intended pending release.
It is idempotent for already tagged releases; never move an existing public tag.
Environment protection is an external setting, not guaranteed by YAML alone. If your
GitHub plan cannot enforce reviewers, workflow dispatch is the manual approval gate;
restrict write access and document that weaker policy before enabling publication.

## CI events and credentials

Preparation uses a scoped `RELEASE_PLEASE_TOKEN`, because GITHUB_TOKEN-created PRs
do not trigger normal PR CI. Prefer a repository-limited GitHub App installation token
if you add an approved token-generation step; otherwise a fine-grained bot PAT is
necessary with the current workflow. No auto-merge. Publication needs no extra token.
Never expose release credentials to fork PR workflows.

## Hotfix and rollback

Create `fix/...` from the default branch, reproduce and fix with tests, merge through
CI, review the next patch release PR and publish through the same manual gate. Do not
manually edit three versions. For a bad release, mark its notes clearly and prepare a
new patch; never retag. Users can select a previous HACS release and restore backups
if storage compatibility requires it. Test a candidate by installing its exact SHA on
a disposable HA instance; record it with [staging results](staging-validation.md).
