#!/usr/bin/env python3
"""Validate a pull request's catalog.yaml against the catalog on main.

Usage: validate_catalog.py <pr-catalog.yaml> <base-catalog.yaml> <pr-files.json>

pr-catalog.yaml is the catalog GitHub's test merge of the pull request into
main would produce, and base-catalog.yaml is main's, so the difference is
exactly what the pull request changes and a duplicate of an entry main
gained since is caught.
pr-files.json is GitHub's pull request files API output, a JSON list.

Environment: FROM_FORK (anything but "false" is treated as a fork, so a
missing value fails closed), GH_TOKEN for the repository lookups.

Exit 0 passes, 1 is an error, 2 is a typosquatting warning (manual review).
This script runs from the base branch and reads the pull request's files as
data only, so a pull request cannot change the rules it is checked against.
"""

import json
import os
import re
import subprocess
import sys

import yaml

VALID_TIERS = {"first-party", "approved", "community"}
ID_PATTERN = re.compile(r"^[a-z0-9-]+$")
SOURCE_PATTERN = re.compile(r"^github:[a-zA-Z0-9_.-]+/branchkit-plugin-[a-zA-Z0-9_.-]+$")


def levenshtein(s1, s2):
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]


def load_plugins(path):
    with open(path) as f:
        cat = yaml.safe_load(f)
    if not isinstance(cat, dict) or not isinstance(cat.get("plugins"), list):
        return None
    return cat["plugins"]


def fork_errors(entries, base, files):
    """What a pull request from a fork may not do.

    A fork pull request is not from a maintainer, so it may only ADD a new
    community entry. Changing or removing an existing entry would let it
    point a listed name at another repository (setting the tier to community
    passes a tier-only rule), so that needs a maintainer.
    """
    errors = []
    for f in files:
        status, name = f.get("status", ""), f.get("filename", "")
        if name != "catalog.yaml" or status not in ("modified", "added"):
            errors.append(f"a pull request from a fork may only change catalog.yaml, not {status} '{name}'")
    new_ids = {e.get("id", "") for e in entries}
    for old_id in base:
        if old_id not in new_ids:
            errors.append(f"plugin '{old_id}': a pull request from a fork may not remove an entry; ask a maintainer")
    for entry in entries:
        plugin_id = entry.get("id", "")
        if plugin_id in base:
            if base[plugin_id] != entry:
                errors.append(f"plugin '{plugin_id}': a pull request from a fork may not change an existing entry; ask a maintainer")
        elif entry.get("tier", "") != "community":
            errors.append(f"plugin '{plugin_id}': a pull request from a fork adds 'community' entries only (this one is '{entry.get('tier', '')}'); a maintainer sets other tiers")
    return errors


def entry_errors(entry, ids_seen, sources_seen):
    """The checks every entry passes, whoever opened the pull request."""
    errors = []
    plugin_id = entry.get("id", "")
    if not isinstance(plugin_id, str) or not ID_PATTERN.match(plugin_id):
        return [f"invalid plugin ID '{plugin_id}' (must be lowercase letters, digits, hyphens)"]
    if plugin_id in ids_seen:
        return [f"duplicate plugin ID '{plugin_id}'"]
    ids_seen.add(plugin_id)

    source = entry.get("source", "")
    tier = entry.get("tier", "")
    if not source:
        errors.append(f"plugin '{plugin_id}': missing 'source' field")
    if not entry.get("description", ""):
        errors.append(f"plugin '{plugin_id}': missing 'description' field")
    if tier not in VALID_TIERS:
        errors.append(f"plugin '{plugin_id}': invalid tier '{tier}' (must be one of: {', '.join(sorted(VALID_TIERS))})")
    if not source:
        return errors

    # first-party means BranchKit's own: the source must be in the
    # branchkit organization, whoever opens the pull request.
    owner = source.removeprefix("github:").split("/")[0].lower()
    if tier == "first-party" and owner != "branchkit":
        errors.append(f"plugin '{plugin_id}': tier 'first-party' needs a source under github:branchkit/, not '{source}'")

    if not SOURCE_PATTERN.match(source):
        errors.append(f"plugin '{plugin_id}': source '{source}' must match github:owner/branchkit-plugin-* format")
        return errors
    if source in sources_seen:
        errors.append(f"plugin '{plugin_id}': duplicate source '{source}'")
    sources_seen.add(source)

    expected_id = source.split("/")[-1].removeprefix("branchkit-plugin-")
    if plugin_id != expected_id:
        errors.append(f"plugin '{plugin_id}': ID must match repo name (repo 'branchkit-plugin-{expected_id}' expects id '{expected_id}')")
    if errors:
        return errors

    owner_repo = source.removeprefix("github:")
    found = subprocess.run(["gh", "api", f"repos/{owner_repo}", "--silent"], capture_output=True)
    if found.returncode != 0:
        return [f"plugin '{plugin_id}': repo '{owner_repo}' not found on GitHub"]
    print(f"pass: plugin '{plugin_id}': {owner_repo} exists")

    manifest = subprocess.run(
        ["gh", "api", f"repos/{owner_repo}/contents/plugin.json",
         "--header", "Accept: application/vnd.github.raw+json"],
        capture_output=True, text=True,
    )
    if manifest.returncode != 0:
        return [f"plugin '{plugin_id}': could not fetch plugin.json from {owner_repo}"]
    try:
        manifest_id = json.loads(manifest.stdout).get("id", "")
    except (json.JSONDecodeError, AttributeError):
        return [f"plugin '{plugin_id}': plugin.json is not a valid JSON object"]
    if manifest_id != plugin_id:
        return [f"plugin '{plugin_id}': plugin.json has id '{manifest_id}', expected '{plugin_id}'"]
    print(f"pass: plugin '{plugin_id}': plugin.json ID matches")
    return []


def typosquat_warnings(ids):
    # The threshold scales with name length to spare short names false positives.
    warnings = []
    ids = sorted(ids)
    for i, id1 in enumerate(ids):
        for id2 in ids[i + 1:]:
            dist = levenshtein(id1, id2)
            min_len = min(len(id1), len(id2))
            threshold = 1 if min_len <= 5 else 2
            if dist <= threshold and min_len > 3:
                warnings.append(f"typosquat risk: '{id1}' and '{id2}' (distance={dist}) — requires manual review")
    return warnings


def main(argv):
    pr_path, base_path, files_path = argv[1:4]
    entries = load_plugins(pr_path)
    if entries is None:
        print("error: catalog.yaml must have a 'plugins' list")
        return 1
    base = {e.get("id", ""): e for e in (load_plugins(base_path) or [])}
    with open(files_path) as f:
        files = json.load(f)

    errors = []
    if os.environ.get("FROM_FORK") != "false":
        errors += fork_errors([e for e in entries if isinstance(e, dict)], base, files)

    ids_seen, sources_seen = set(), set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append(f"every catalog entry must be a mapping, not {entry!r}")
            continue
        errors += entry_errors(entry, ids_seen, sources_seen)

    warnings = typosquat_warnings(ids_seen)
    for e in errors:
        print(f"error: {e}")
    for w in warnings:
        print(f"warning: {w}")
    print(f"\nValidated {len(entries)} plugins: {len(errors)} errors, {len(warnings)} warnings")
    if errors:
        return 1
    if warnings:
        print("Typosquat warnings present — PR requires manual review")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
