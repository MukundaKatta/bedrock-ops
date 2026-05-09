# Submitting to a Launchpad PPA

A Personal Package Archive (PPA) on Launchpad lets you publish `.deb` packages without going through Debian's mainline-archive review.

## One-time setup

1. Create a Launchpad account at <https://launchpad.net/+login>
2. Generate a GPG key and upload it: <https://help.launchpad.net/YourAccount/ImportingYourPGPKey>
3. Sign the Code of Conduct (required before PPA creation): <https://launchpad.net/codeofconduct>
4. Create a PPA at <https://launchpad.net/~mukundakatta/+activate-ppa> — name suggestion: `agent-stack`
5. Install Debian packaging tools on a Debian/Ubuntu machine:

   ```bash
   sudo apt install devscripts debhelper dh-python pybuild-plugin-pyproject dput
   ```

## Submitting this package

```bash
# 1. Download the upstream sdist as the "orig" tarball:
mkdir -p /tmp/build && cd /tmp/build
wget -O python-bedrock-ops_0.1.0.orig.tar.gz \
    https://github.com/MukundaKatta/bedrock-ops/releases/download/v0.1.0/bedrock_ops-0.1.0.tar.gz

# 2. Unpack and copy the staged debian/ in:
tar xzf python-bedrock-ops_0.1.0.orig.tar.gz
cd bedrock_ops-0.1.0
cp -r /path/to/this/repo/packaging/debian/ .

# 3. Build a SOURCE package (not binary; PPA builds happen on Launchpad):
debuild -S -sa

# 4. Upload to your PPA:
cd ..
dput ppa:mukundakatta/agent-stack python-bedrock-ops_0.1.0-1_source.changes
```

## After build succeeds (Launchpad emails you when done)

Users install via:

```bash
sudo add-apt-repository ppa:mukundakatta/agent-stack
sudo apt update
sudo apt install python3-bedrock-ops
```

## Updating

When the upstream library bumps version:

1. Add a new entry at the top of `debian/changelog` (`dch -i` is the canonical way)
2. Re-build the orig tarball (or update Source0)
3. `debuild -S -sa` and `dput` again

## Targeting multiple Ubuntu releases

To build for jammy (22.04), noble (24.04), and bookworm (Debian 12), you'll need to either:
- Maintain separate `debian/changelog` entries per series and dput each one, OR
- Use `backportpackage` from `ubuntu-dev-tools` to auto-target multiple series

The `jammy` distribution name in our changelog is the default; change to `noble`/`bookworm` for those targets.
