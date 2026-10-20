# Final remediation evidence — 2026-10-20

Started clean at audited `7a673deeb1155ee33a3f2a7ac433765cd065c1f1`.
GitHub REST confirmed default branch main, no master branch, no tags and no releases.
The local working branch remained master; no remote branch was changed.

## Confirmed fixes

- Contextual help used a nonexistent branch. Centralized deterministic main URLs and
  offline repository/branch/file/anchor checks now cover all eight forms and EN/NL
  placeholders. Issue-template links also use main. Upstream Hassfest's own master
  action ref is unrelated and intentionally retained.
- Release preparation passed an absent secret to the action. It now fails explicitly
  before invoking Release Please, with setup instructions and no token fallback.
- Ordinary main pushes ran Quality twice. Preparation now consumes successful trusted
  Quality push completion; manual publication alone intentionally reruns Quality.
- The publication guard's version-body parser did not match Release Please's actual
  Markdown linked heading. The real-library fixture exposed and fixed that defect.
- Native dashboard comes first; Waze region labels match HA Core 2026.10.2 source.
  EV descriptions explain disabled/home-only behavior without extra forms or resets.

## Verification

311 tests passed with 86.44% runtime statement coverage before final validator-only
hardening; 85% minimum retained. Editable install, pip check, wheel build/content,
Ruff/format, Mypy (14 modules), translation/manifest, release/docs checks, actionlint
1.7.12 and Docker Hassfest (one integration, zero invalid) passed.
Local HACS stops at missing GITHUB_TOKEN, not a reported integration-validation failure.
Hosted HACS was reported passing at the baseline; this unpushed branch has no hosted run.

Real Release Please 17.3.0 (v4 action dependency) passed the isolated nonpublishing
fixture: bootstrap cutoff, forced first 1.0.0, generated PR metadata/notes, all five
version updaters including Python marker, candidate tag/SHA, repeat preparation,
no-change post-release and future patch/minor after removing the pin. Fake GitHub has
no write methods and no network. Fixture is now part of Quality. Bootstrap creates
a same-version compare link; maintainer review must remove that link and add the older
functionality summary. No production dry-run with credentials or real PR was created.

## Remaining gates and review

Live PAT authorization, PR CI event delivery, merge metadata, protected environment
approval, publication and HACS download require maintainer execution. No secrets or
settings were created. Exact steps are in repository-setup.md. Publication fails if
main advanced beyond the release PR merge: this deliberate restriction avoids tagging
untested ordinary commits. Merge/squash/rebase resulting-tip REST semantics are accepted;
changed label/title/branch conventions require guard/fixture updates.

Preparation accepts only same-repository successful push Quality on main, never PR/fork
heads, and consumes no artifacts or checkout with credentials. A HEAD check rejects
outdated completions; concurrency serializes release jobs. GitHub API reads/action
writes are not an atomic branch lock: maintainers must freeze merges during preparation
and publication. This narrow external-change race is not claimed eliminated by YAML.
No automatic publication path exists; dispatch publish=true and passing exact-SHA
Quality are required, with environment approval only if externally configured.

Real HAOS graphical forms/brand rendering, process restart staging and real EV sessions
were not run. EV remains optional/experimental; provider ambiguity remains fail-closed.
Entity unique IDs, storage schemas/history and configuration keys were not changed.
