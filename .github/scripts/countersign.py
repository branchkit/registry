#!/usr/bin/env python3
"""Counter-sign catalog entries that have a published release.

For each entry with a `source`, fetch its latest release, extract the
plugin.json from a release tarball, and record BranchKit's registry
counter-signature over that manifest (via `branchkit-cli registry sign`).
Idempotent: an entry whose recorded signature already matches its current
released manifest is left untouched, so a no-op run makes no commit.

The counter-signature binds the MANIFEST hash only (id + publisher live in
plugin.json) — platform- and version-independent, so one signature covers
every platform artifact and survives new releases that don't change the
manifest. See DESIGN_PLUGIN_SIGNING_CHAIN.md.

Run in the trusted main-branch workflow only (needs BRANCHKIT_REGISTRY_KEY).
"""

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile

from ruamel.yaml import YAML

CATALOG = "catalog.yaml"


def gh_json(args):
    """Run a gh command returning JSON, or None on failure."""
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def released_manifest(owner_repo, plugin_id, workdir):
    """Download a release tarball for plugin_id and return its plugin.json path,
    or None when there's no usable release."""
    assets = gh_json(["gh", "release", "view", "--repo", owner_repo,
                      "--json", "assets", "--jq", ".assets"])
    if not assets:
        return None
    prefix = f"branchkit-plugin-{plugin_id}-"
    tarball = next((a["name"] for a in assets
                    if a["name"].startswith(prefix) and a["name"].endswith(".tar.gz")), None)
    if not tarball:
        return None
    r = subprocess.run(
        ["gh", "release", "download", "--repo", owner_repo,
         "--pattern", tarball, "--dir", workdir, "--clobber"],
        capture_output=True, text=True)
    if r.returncode != 0:
        return None
    tar_path = os.path.join(workdir, tarball)
    try:
        with tarfile.open(tar_path) as tf:
            member = next((m for m in tf.getmembers()
                           if os.path.basename(m.name) == "plugin.json"), None)
            if member is None:
                return None
            member.name = "plugin.json"  # flatten
            tf.extract(member, workdir, filter="data")
    except (tarfile.TarError, OSError):
        return None
    return os.path.join(workdir, "plugin.json")


def sign_manifest(manifest_path):
    """Run `branchkit-cli registry sign` and return (manifest_sha256, signature)."""
    r = subprocess.run(
        ["branchkit-cli", "registry", "sign", "--manifest", manifest_path],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"registry sign failed: {r.stderr.strip()}")
    fields = {}
    for line in r.stdout.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields.get("manifest_sha256", ""), fields.get("registry_signature", "")


def main():
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # keep long hashes/signatures on one line, not wrapped
    with open(CATALOG) as f:
        cat = yaml.load(f)

    if not cat or "plugins" not in cat:
        print("catalog.yaml has no plugins")
        return 0

    changed = 0
    for entry in cat["plugins"]:
        plugin_id = entry.get("id", "")
        source = entry.get("source", "")
        if not source or not source.startswith("github:"):
            continue
        owner_repo = source[len("github:"):]

        with tempfile.TemporaryDirectory() as workdir:
            manifest_path = released_manifest(owner_repo, plugin_id, workdir)
            if manifest_path is None:
                print(f"skip {plugin_id}: no usable release")
                continue

            manifest_bytes = open(manifest_path, "rb").read()
            manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()

            # Idempotent: already counter-signed this exact manifest.
            if (entry.get("manifest_sha256") == manifest_hash
                    and entry.get("registry_signature")):
                print(f"ok   {plugin_id}: signature current")
                continue

            try:
                signed_hash, sig = sign_manifest(manifest_path)
            except RuntimeError as e:
                print(f"error {plugin_id}: {e}")
                return 1
            if signed_hash != manifest_hash or not sig:
                print(f"error {plugin_id}: sign output inconsistent")
                return 1

            entry["manifest_sha256"] = manifest_hash
            entry["registry_signature"] = sig
            changed += 1
            print(f"sign {plugin_id}: counter-signed")

    if changed:
        with open(CATALOG, "w") as f:
            yaml.dump(cat, f)
        print(f"\nCounter-signed {changed} entr{'y' if changed == 1 else 'ies'}.")
    else:
        print("\nNothing to sign.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
