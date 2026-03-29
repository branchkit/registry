# BranchKit Plugin Registry

This repository contains the plugin registry for [BranchKit](https://github.com/branchkit). It maps short plugin names to their GitHub sources, enabling:

```bash
branchkit-cli plugin install voice
```

instead of:

```bash
branchkit-cli plugin install branchkit/branchkit-plugin-voice
```

## Registry format

`registry.json` maps plugin IDs to their sources:

```json
{
  "version": 1,
  "plugins": {
    "my-plugin": {
      "source": "owner/branchkit-plugin-my-plugin",
      "description": "What it does.",
      "categories": ["category"],
      "verified": false
    }
  }
}
```

Fields:
- **source** (required) — GitHub `owner/repo`
- **description** (required) — one-liner for search/browse
- **categories** (optional) — tags for filtering
- **verified** (default false) — `true` for plugins published by the `branchkit` org or reviewed by maintainers

## Adding a plugin

1. Fork this repository
2. Add your plugin to `registry.json`
3. Open a pull request

Requirements:
- Plugin repo must exist and contain a valid `plugin.json`
- Plugin ID must be lowercase letters, digits, and hyphens (`[a-z0-9-]+`)
- Plugin repo should follow the `branchkit-plugin-{name}` naming convention
- Description should be a single sentence

## How it works

The [branchkit-cli](https://github.com/branchkit/branchkit-cli) fetches this registry to resolve short names to GitHub sources. The registry is a name mapping, not a package host — all artifacts live in GitHub Releases.
