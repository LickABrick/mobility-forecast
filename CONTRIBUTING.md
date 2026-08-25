# Contributing

## Change flow

1. Start from a clean, current `main`.
2. Create a focused branch for human/remote collaboration; unattended local phase work may use local `main` as documented in `AGENTS.md`.
3. Add or update behavior tests first where practical.
4. Implement one coherent change.
5. Run `python scripts/check_checkpoint.py` and the relevant test suite.
6. Review the complete diff for secrets, personal data, accidental API calls and scope creep.
7. Commit with Conventional Commits.

## Conventional Commits

Format:

```text
type(scope): imperative summary

Optional body explaining why, constraints and compatibility effects.
```

Examples:

```text
docs(architecture): define forecast profile boundaries
feat(filters): add deterministic calendar exclusion rules
test(location): cover stale vehicle tracker fallback
fix(routes): preserve unavailable route state
ci(quality): validate HACS and Python checks
```

Breaking changes use `!` and a `BREAKING CHANGE:` footer. They require a storage/config migration and dedicated tests.

## Commit quality

A commit must:

- have one purpose and be independently reviewable;
- leave the repository in a verified state;
- include tests or explain why no executable behavior changed;
- update affected documentation and project status;
- contain no secrets or user-specific calendar/location data;
- avoid drive-by formatting or unrelated refactors.

## Reviews and merges

When a remote is introduced, changes should use short-lived branches and pull requests. Require passing CI, an up-to-date base, review of privacy/safety impact and a squash or rebase policy chosen once for the project. Do not mix merge styles unpredictably. Preserve useful authorship and traceability.

## Configuration and migrations

Config-entry data, options and storage are versioned contracts. Any schema/default change must include:

- explicit old and new behavior;
- migration implementation;
- migration and rollback tests;
- release-note documentation;
- redaction review for diagnostics.
