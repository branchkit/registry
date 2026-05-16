# BranchKit Plugin Catalog

This repository contains the plugin catalog for [BranchKit](https://github.com/branchkit). It maps short plugin names to their GitHub sources and provides trust tier information.

```bash
branchkit-cli plugin install keyboard
# resolves via catalog → github:branchkit/branchkit-plugin-keyboard
```

For unlisted plugins, use the full source URL:

```bash
branchkit-cli plugin install github:somedev/branchkit-plugin-foo
```

## Catalog format

`catalog.yaml` lists all known plugins:

```yaml
plugins:
  - id: my-plugin
    source: github:owner/branchkit-plugin-my-plugin
    description: "What it does."
    categories: [category]
    tier: community
```

Fields:
- **id** (required) — plugin ID, lowercase letters, digits, and hyphens
- **source** (required) — `github:owner/branchkit-plugin-{id}` format
- **description** (required) — one-liner
- **categories** (required) — tags for filtering
- **tier** (required) — `first-party`, `approved`, or `community`

## Adding a plugin

1. Fork this repository
2. Add your plugin entry to `catalog.yaml`
3. Open a pull request

CI validates your submission automatically:
- Repo must exist and contain a valid `plugin.json`
- Plugin ID in `plugin.json` must match the `id` field in the catalog
- Repo must follow `branchkit-plugin-{name}` naming convention
- No ID conflicts with existing entries
- No typosquatting (Levenshtein distance check against existing names)

**CI green + no typosquat flag = auto-merge as `tier: community`.** No manual review needed for listing.

## Trust tiers

| Tier | Meaning |
|------|---------|
| `first-party` | Published by the `branchkit` org |
| `approved` | Reviewed and endorsed by BranchKit maintainers |
| `community` | Listed, CI-validated, not yet reviewed |

## How it works

The [branchkit-cli](https://github.com/branchkit/branchkit-cli) fetches this catalog to resolve short names to GitHub sources. The catalog is a name mapping with trust metadata — all artifacts live in GitHub Releases.
