# Releasing the pywry plugin

Step-by-step for cutting a new version. Assumes `main` is up to date
with everything the release should ship.

## 1. Decide the version bump

Follow the policy in [claude/CONTRIBUTING.md](../../CONTRIBUTING.md#versioning).
Summary:

- Patch: bug fix, doc, tightening an existing skill.
- Minor: new command / skill / agent / hook / MCP tool.
- Major: rename, remove, breaking contract change.

## 2. Update the version in both manifests

Edit:

1. [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) → `"version": "…"`
2. [`claude/.claude-plugin/marketplace.json`](../../.claude-plugin/marketplace.json)
   → `plugins[name=pywry].version`

Both must match. CI enforces this.

## 3. Update the changelog

Edit [CHANGELOG.md](CHANGELOG.md):

- Move everything from `## [Unreleased]` into a new
  `## [<version>] — <YYYY-MM-DD>` section.
- Put an empty `## [Unreleased]` back at the top.
- Keep sub-headers (`### Added`, `### Changed`, `### Fixed`,
  `### Removed`, `### Documentation`).

## 4. Commit

```bash
git add claude/plugins/pywry/.claude-plugin/plugin.json \
        claude/.claude-plugin/marketplace.json \
        claude/plugins/pywry/CHANGELOG.md
git commit -m "Release claude/plugins/pywry v<version>"
```

## 5. Tag

```bash
git tag -a plugin-pywry-v<version> -m "pywry plugin v<version>"
git push origin main plugin-pywry-v<version>
```

Tag prefix `plugin-pywry-v` keeps these distinct from PyWry Python
package tags (`v2.0.0` etc.), so releases in the two trees don't
collide.

## 6. (Optional) Draft a GitHub release

```bash
gh release create plugin-pywry-v<version> \
  --title "pywry plugin v<version>" \
  --notes-file <(sed -n "/## \[<version>\]/,/## \[/p" claude/plugins/pywry/CHANGELOG.md | head -n -1)
```

## 7. Announce

Post the install command to the relevant channels:

```
/plugin marketplace add deeleeramone/PyWry --path claude/.claude-plugin/marketplace.json
/plugin install pywry@pywry --version plugin-pywry-v<version>
```

## 8. Verify

In a fresh Claude Code session:

- `/mcp` lists `pywry` as connected.
- `/pywry:doctor` reports green.
- `/mcp tools pywry` shows ≥ 66 tools including `get_widget_app`.
