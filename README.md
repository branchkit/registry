# BranchKit plugin registry

The public plugin catalog for [BranchKit](https://github.com/branchkit), an
accessibility plugin platform for the desktop. It maps short plugin names to
their GitHub sources, records a trust tier for each, and carries the blocklist
and the shared release action that plugins publish with.

[branchkit-cli](https://github.com/branchkit/branchkit-cli) reads it:

```bash
branchkit-cli plugin install keyboard
# resolves through catalog.yaml to github:branchkit/branchkit-plugin-keyboard
```

A plugin that is not listed installs by its source:

```bash
branchkit-cli plugin install github:somedev/branchkit-plugin-foo
```

The catalog is a name mapping with trust metadata. The plugins themselves are
downloaded from each plugin's GitHub Releases.

**Status.** BranchKit is pre-launch. No plugin in the catalog has published a
release yet, so installing by catalog name does not succeed today, and some
first-party entries point at repositories that stay private until launch.

## What is here

| Path | What it is |
|---|---|
| `catalog.yaml` | The catalog |
| `blocklist.json` | Sources the CLI refuses to install |
| `release-action/` | The shared GitHub Action that packages, signs and uploads a plugin release |
| `workflows/release.yml` | A release workflow to copy into a plugin repository |
| `workflows/conformance.yml` | A conformance-check workflow to copy into a plugin repository |
| `.github/` | This repository's own automation: catalog validation, counter-signing, the stale-entry check |

## Catalog format

```yaml
plugins:
  - id: my-plugin
    source: github:owner/branchkit-plugin-my-plugin
    description: "What it does."
    categories: [category]
    tier: community
```

| Field | |
|---|---|
| `id` | Required. The plugin's ID: lowercase letters, digits and hyphens. Must equal the `id` in the plugin's `plugin.json` and the repository name after `branchkit-plugin-` |
| `source` | Required. `github:owner/branchkit-plugin-<id>` |
| `description` | Required. One line |
| `categories` | Tags for filtering |
| `tier` | Required. `first-party`, `approved` or `community` |
| `collections` | Optional. Bare collection names the plugin introduces, so authors can find an existing vocabulary before inventing a rival name (`branchkit-cli plugin package` warns on overlap) |
| `manifest_sha256`, `registry_signature` | Written by automation, never by hand. See [Counter-signature](#counter-signature) |

## Adding a plugin

1. Fork this repository.
2. Add an entry to `catalog.yaml` with `tier: community`.
3. Open a pull request.

CI checks the submission:

- the ID format, and no duplicate IDs or sources;
- `source` matches `github:owner/branchkit-plugin-*`, and the ID matches the
  repository name;
- the repository exists and has a `plugin.json` at its root whose `id` matches;
- a pull request from a fork adds or changes `community` entries only;
  maintainers set the other tiers;
- `first-party` entries point under `github:branchkit/`;
- no ID is within a small edit distance of another (a typosquatting check).

A fork pull request that passes with no typosquatting warning is merged
automatically as `community`. A warning holds it for manual review.

## Trust tiers

| Tier | Meaning |
|---|---|
| `first-party` | Published by the `branchkit` organization |
| `approved` | Reviewed and endorsed by BranchKit maintainers |
| `community` | Listed and CI-validated, not reviewed |

## Releasing a plugin

`release-action/` is a composite action that runs inside your own release job.
You build the binary, in any language; the action does the rest: a
reproducible tarball named `branchkit-plugin-<name>-<os>-<arch>.tar.gz`, its
`.sha256` checksum, a Sigstore attestation (keyless, under your repository's
own GitHub identity) and the upload to the GitHub release. Call it once per
target platform. `workflows/release.yml` is a complete workflow to copy; the Go
template from `branchkit-cli dev init` includes the same job.

Set `publisher` in your `plugin.json` to `"github:YOUR-ORG"`. At install, the
CLI checks the attestation against it and refuses a plugin whose attestation
contradicts the publisher it claims. Unsigned plugins still install, as
unsigned.

`workflows/conformance.yml` runs `branchkit-cli dev test . --static-only` on
every release tag. At install, the CLI reads that check's result for the tag
being installed and shows it.

Both workflows and the release action download a released `branchkit-cli`
binary. None is published yet, so they cannot complete until one is.

## Counter-signature

A maintainer runs the counter-sign workflow by hand on `main` (it no longer
runs on every catalog change). It signs the manifest of each entry that has a
release and writes `manifest_sha256` and `registry_signature`
into the entry. Installing by catalog name checks that signature, so a copy of
a plugin republished under another name cannot claim the listing. A present but
invalid signature is refused. The signing key exists only in this repository's
Actions secrets and is never available to pull requests.

## Blocklist

`blocklist.json` lists sources flagged as malicious or harmful:

```json
{
  "blocked": [
    { "source": "github:badactor/branchkit-plugin-malware", "reason": "Exfiltrates keystrokes" }
  ],
  "updated_at": "2026-05-16T00:00:00Z"
}
```

`branchkit-cli plugin install` refuses a blocklisted source unless given
`--force`, and `branchkit-cli plugin check-blocklist` checks plugins already
installed. Entries are added when a problem is reported; to flag a plugin, open
an issue on this repository.

## Stale entries

A weekly job opens a pull request removing entries whose repository is archived
or no longer has a `plugin.json`. A repository it cannot read (private,
deleted or renamed) is not treated as stale.

## License

MIT
