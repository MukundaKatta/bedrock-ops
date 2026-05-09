# Packaging recipes

Distribution-specific packaging files for `bedrock-ops`. Each subdirectory contains a recipe + a `SUBMIT.md` walking through the submission flow.

| Directory | Target | Status | Submit-side action required |
|---|---|---|---|
| `aur/` | Arch User Repository | drafted | Arch account + SSH key. `git push` to `aur@aur.archlinux.org:python-bedrock-ops.git` |
| `copr/` | Fedora Copr | drafted | Fedora Account System login. `copr-cli build` |
| `debian/` | Launchpad PPA (Ubuntu/Debian) | drafted | Launchpad account + GPG key. `debuild -S -sa && dput` |

For Homebrew, see the open PR at <https://github.com/MukundaKatta/homebrew-tools/pull/1>.

For nixpkgs, see PR <https://github.com/NixOS/nixpkgs/pull/518492>.

## Why these are staged not submitted

Each ecosystem requires a separate maintainer account + auth flow that this repo cannot complete on its own:

- AUR needs an Arch user account and an SSH key registered against it. PKGBUILDs are staged here ready to `git push` once you've gone through that flow.
- Copr needs a Fedora Account System (FAS) login and an API token. The `.spec` is staged here.
- Launchpad PPA needs a verified GPG key and signed Code of Conduct. The `debian/` is staged here.

The recipes are version-locked to v0.1.0. When the upstream version bumps, update the `pkgver`/`Version`/`changelog` entry and the `sha256`/`Source0` URL in each.

## Distribution channels intentionally NOT covered

| Platform | Reason |
|---|---|
| Homebrew core | Library-only formulas are explicitly rejected by Homebrew core's policy |
| Debian/Ubuntu/Fedora/Arch mainline | Multi-month sponsored-maintainer review process; user-channels (PPA, Copr, AUR) cover the same audience |
| Chocolatey, Scoop, winget | Wrong category — these are for end-user Windows applications (`.exe` / `.msi`), not Python libraries |
| Docker Hub, GHCR, Quay | Libraries aren't distributed as containers |
| Helm, Artifact Hub | Wrong artifact type (k8s charts) |
| Conan, vcpkg | C/C++ only |
| RubyGems, Packagist, NuGet, Maven, Hex, CPAN, Hackage, OPAM, pub.dev, npm, JSR | Wrong language; these are not redistribution channels for Python libraries — they require an actual port written in the target language |
