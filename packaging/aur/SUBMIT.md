# Submitting to AUR

## One-time setup (per machine)

```bash
# 1. Create an account at https://aur.archlinux.org/register
# 2. Add an SSH key at https://aur.archlinux.org/account/<username>/edit
# 3. Configure git to use that SSH key for AUR:
cat >> ~/.ssh/config <<EOF
Host aur.archlinux.org
  IdentityFile ~/.ssh/aur
  User aur
EOF
```

## Submitting this package

```bash
# Clone the empty AUR repo (you must have ssh access):
git clone ssh://aur@aur.archlinux.org/python-bedrock-ops.git /tmp/aur-bedrock-ops
cd /tmp/aur-bedrock-ops

# Copy the staged files in:
cp /path/to/this/repo/packaging/aur/PKGBUILD .
cp /path/to/this/repo/packaging/aur/.SRCINFO .

# Sanity check (optional, requires Arch / makepkg):
makepkg --printsrcinfo > .SRCINFO        # regenerate to be safe
namcap PKGBUILD                          # lint
makepkg -si                              # build + install locally to verify

# Push to AUR:
git add PKGBUILD .SRCINFO
git commit -m "Initial: 0.1.0"
git push origin master
```

## Updating

When the upstream library version changes:

1. Bump `pkgver=` in `PKGBUILD`.
2. Update the `sha256sums=` line for the new GitHub Release sdist.
3. Regenerate `.SRCINFO`: `makepkg --printsrcinfo > .SRCINFO`
4. Commit and push.
