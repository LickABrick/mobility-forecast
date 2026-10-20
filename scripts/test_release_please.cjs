/* Nonpublishing Release Please fixture. Install pinned npm dependency outside repo:
 * npm install --prefix /tmp/opencode/release-fixture release-please@17.3.0
 * NODE_PATH=/tmp/opencode/release-fixture/node_modules node scripts/test_release_please.cjs
 * Only build* APIs are used; fake GitHub has no write methods or network access.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {Manifest} = require('release-please');
const root = path.resolve(__dirname, '..');
const sha = 'a'.repeat(40);
const files = new Map();
for (const name of ['release-please-config.json', '.release-please-manifest.json', 'version.txt', 'CHANGELOG.md', 'custom_components/mobility_forecast/manifest.json', 'pyproject.toml', 'custom_components/mobility_forecast/const.py']) {
  files.set(name, fs.readFileSync(path.join(root, name), 'utf8'));
}
let releases = [], tags = [], merged = [];
let commits = [
  {sha, message: 'feat: native configuration polish', files: ['custom_components/mobility_forecast/config_flow.py']},
  {sha: 'b'.repeat(40), message: 'fix: honor forecast days', files: ['custom_components/mobility_forecast/services.py']},
  {sha: JSON.parse(files.get('release-please-config.json'))['bootstrap-sha'], message: 'feat: excluded bootstrap baseline', files: ['README.md']},
];
const github = {
  repository: {owner: 'LickABrick', repo: 'mobility-forecast', defaultBranch: 'main'},
  getFileJson: async name => JSON.parse(files.get(name)),
  getFileContentsOnBranch: async name => ({parsedContent: files.get(name), content: Buffer.from(files.get(name)).toString('base64'), sha}),
  releaseIterator: async function* () {yield* releases;},
  tagIterator: async function* () {yield* tags;},
  mergeCommitIterator: async function* () {yield* commits;},
  pullRequestIterator: async function* () {yield* merged;},
};
async function manifest() {return Manifest.fromManifest(github, 'main');}
function apply(pr) {
  for (const update of pr.updates) {
    const before = files.get(update.path);
    files.set(update.path, update.updater.updateContent(before));
  }
}
function versions(expected) {
  assert.equal(files.get('version.txt').trim(), expected);
  assert.equal(JSON.parse(files.get('custom_components/mobility_forecast/manifest.json')).version, expected);
  assert.ok(files.get('pyproject.toml').includes(`version = "${expected}"`));
  assert.ok(files.get('custom_components/mobility_forecast/const.py').includes(`VERSION = "${expected}"  # x-release-please-version`));
  assert.equal(JSON.parse(files.get('.release-please-manifest.json'))['.'], expected);
}
(async () => {
  const first = await (await manifest()).buildPullRequests();
  assert.equal(first.length, 1);
  const pr = first[0];
  assert.equal(pr.version.toString(), '1.0.0');
  assert.equal(pr.title.toString(), 'chore(main): release 1.0.0');
  assert.equal(pr.headRefName, 'release-please--branches--main');
  assert.ok(pr.labels.includes('autorelease: pending'));
  const body = pr.body.toString();
  assert.ok(body.includes('1.0.0'));
  assert.ok(body.includes('honor forecast days'));
  assert.ok(!body.includes('excluded bootstrap baseline'));
  apply(pr); versions('1.0.0');
  assert.match(files.get('CHANGELOG.md'), /^## (?:\[)?1\.0\.0/m);
  // Same input produces the same candidate version, not an accidental minor bump.
  assert.equal((await (await manifest()).buildPullRequests())[0].version.toString(), '1.0.0');
  merged = [{number: 12, sha, title: pr.title.toString(), body, labels: pr.labels, headBranchName: pr.headRefName, baseBranchName: 'main', mergeCommitOid: sha, files: pr.updates.map(u => u.path)}];
  // Exercise the same REST projection used by the Python publication guard.
  const {spawnSync} = require('node:child_process');
  const snapshot = {repository: 'LickABrick/mobility-forecast', branch: 'main', default_branch: 'main', sha, head: sha, version: '1.0.0', approved: true, tags: [], prs: [{number: 12, merged_at: '2026-10-20', base: {ref: 'main', repo: {full_name: 'LickABrick/mobility-forecast'}}, head: {ref: pr.headRefName, repo: {full_name: 'LickABrick/mobility-forecast'}}, merge_commit_sha: sha, title: pr.title.toString(), body, labels: pr.labels.map(name => ({name}))}]};
  const checked = spawnSync(process.env.PYTHON || path.join(root, '.venv314/bin/python'), ['-c', 'import json,sys; from scripts.check_release_candidate import validate_candidate; validate_candidate(**json.load(sys.stdin))'], {cwd: root, input: JSON.stringify(snapshot), encoding: 'utf8'});
  assert.equal(checked.status, 0, checked.stderr);
  const candidates = await (await manifest()).buildReleases();
  assert.equal(candidates.length, 1);
  assert.equal(candidates[0].tag.toString(), 'v1.0.0');
  assert.equal(candidates[0].sha, sha);
  console.log(JSON.stringify({title: pr.title.toString(), branch: pr.headRefName, labels: pr.labels, version: candidates[0].tag.version.toString()}));
  // Simulate the published lifecycle, remove the bootstrap pin, then test patch/minor.
  const config = JSON.parse(files.get('release-please-config.json'));
  delete config.packages['.']['release-as'];
  files.set('release-please-config.json', JSON.stringify(config));
  releases = [{tagName: 'v1.0.0', sha, notes: 'First public release'}];
  tags = [{name: 'v1.0.0', sha}];
  merged = [];
  commits = [{sha, message: pr.title.toString(), files: pr.updates.map(u => u.path)}];
  assert.equal((await (await manifest()).buildPullRequests()).length, 0);
  for (const [message, expected] of [['fix: next fix', '1.0.1'], ['feat: next feature', '1.1.0']]) {
    commits.unshift({sha: 'c'.repeat(40), message, files: ['README.md']});
    const next = (await (await manifest()).buildPullRequests())[0];
    assert.equal(next.version.toString(), expected);
    apply(next); versions(expected);
    // Restore previous version manifest for independent bump from 1.0.0.
    files.set('.release-please-manifest.json', '{".":"1.0.0"}');
    commits.shift();
  }
  console.log('PASS: actual Release Please bootstrap, notes, labels, merged candidate, all updaters, repeat/no-change, patch and minor (no writes/network).');
})().catch(error => {console.error(error); process.exit(1);});
