# Controlled releases

Release Please action v4 prepares one root release PR. `version.txt` is canonical;
Release Please atomically updates manifest JSON, project TOML, the annotated runtime
constant and its release manifest. CI checks parity. No runtime GitHub requests or
TOML parsing are added to the integration.

## Bootstrap

The first public target is intentionally **1.0.0**, matching existing metadata.
`bootstrap-sha` stops notes at the audited pre-polish baseline. The manifest already
says 1.0.0, so `release-as: 1.0.0` is necessary to avoid an unintended feature bump.
With this configuration Release Please can generate a same-version comparison link
in initial notes; replace that misleading comparison link during release PR review
and add a human summary of pre-bootstrap functionality. Generated commits only cover
changes after the bootstrap SHA.

After publishing 1.0.0, remove `release-as` and optionally `bootstrap-sha` in the next
maintenance PR **before preparing another release**. Otherwise version forcing would
continue. Never reset the release manifest to pretend a release has not happened.

## Events and authorization

1. Pull requests run normal Quality. Pushes to `main` run one normal Quality workflow.
2. Release preparation receives Quality's `workflow_run: completed`, but only accepts
   successful **push** runs on this repository's verified default branch `main`.
   Fork/PR events cannot reach the preparation credential. It checks the validated
   SHA is still main HEAD; outdated completions skip with an explicit notice.
3. Preparation has no checkout, artifact download or execution of triggering-head code.
   It uses repository secret `RELEASE_PLEASE_TOKEN`. Missing secret fails explicitly:
   no release PR was created by that run. There is no GITHUB_TOKEN fallback.
4. Release Please creates/updates a PR, never publishes automatically. Preparation and
   publication share serialized concurrency. Do not merge while preparation is running:
   GitHub cannot atomically lock a branch between the HEAD check and the action's API
   reads. A later push must pass its own Quality before a subsequent preparation.
5. Review the release PR and required CI, then merge it. Do not merge ordinary commits
   between the release PR and publication. If that happens, publication fails closed;
   prepare/merge a new release PR for the newer code rather than bypassing the guard.
6. Actions → **Release → Run workflow**, branch **main**, enable `publish`. This explicit
   dispatch is required even if environment protections are unavailable. Publication
   reruns full Quality against the dispatch SHA; this rerun is deliberate, not duplicate
   push CI. Failed Quality prevents the write-capable job.
7. If configured, approve the `release` environment. The job verifies current HEAD,
   version/changelog, exactly one pending merged Release Please root PR, its generated
   branch/title/body and merge commit identity, and absence of the version tag. GitHub's
   REST merge_commit_sha represents the resulting tip for merge/squash/rebase merges.
   Label configuration is deliberately fixed to Release Please's default pending label;
   changes to labels/title/branch patterns require updating guards and fixtures together.
8. A final HEAD check precedes Release Please's release-only invocation. Never move
   public tags. Existing tags and repeat publication requests are rejected, not overwritten.
   As with any API-based process there is a narrow external-change race: freeze merges
   during approval/publication. Branch rules and write-access restrictions remain essential.

Publication uses job-scoped GITHUB_TOKEN, with Contents, Issues and Pull requests write
for releases/comments/labels. Preparation's fine-grained PAT triggers normal PR CI;
a GitHub App installation token is a future alternative with better rotation but an
additional generation step. No credentials are exposed to untrusted PR execution.
GITHUB_TOKEN-created tag/release events do not trigger downstream release workflows;
validation therefore occurs before publication, not in a later tag workflow.

## Nonpublishing verification

The checked-in fixture uses real Release Please **17.3.0**, matching the v4 action's
current library dependency, with a read-only fake GitHub interface. No token or network
is used by the fixture; npm installation needs public package access.

```bash
npm install --prefix /tmp/opencode/release-fixture --ignore-scripts release-please@17.3.0
NODE_PATH=/tmp/opencode/release-fixture/node_modules node scripts/test_release_please.cjs
```

Use `PYTHON=python` if not using the repository's `.venv314`. CI runs this fixture.
It verifies first PR version/title/branch/label/notes, bootstrap cutoff, all five version
files, the actual generated PR body through the Python candidate guard, merged release
candidate SHA/tag, repeat preparation, no-change after publication and future patch/minor
bumps after removing the pin. There are no fake GitHub write methods.

This is **not** end-to-end GitHub verification. PAT authorization, real PR checks,
merge metadata, environment permissions, live publication and HACS detection still need
maintainer verification. A supported CLI dry-run also needs GitHub credentials; do not
place tokens on command lines or use production for experimental tags.

## Hotfix and rollback

Branch `fix/...` from main, reproduce/fix with tests, merge through required checks,
review the generated patch release PR and use the same dispatch gate. Features normally
select minor versions; breaking Conventional Commits select major. Never manually bump
three files independently. For a faulty release, clarify release notes and issue a new
patch; users may select an older HACS release and restore backups where necessary.
Test exact candidate SHAs using [staging validation](staging-validation.md).
