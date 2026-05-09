# Submitting to Fedora Copr

Copr is Fedora's user-driven build/repo service. Anyone with a Fedora Account System (FAS) account can publish packages.

## One-time setup

1. Create a FAS account at <https://accounts.fedoraproject.org/>
2. Sign in to <https://copr.fedorainfracloud.org/>
3. Install the Copr CLI on your Fedora workstation: `sudo dnf install copr-cli`
4. Get an API token at <https://copr.fedorainfracloud.org/api/> and save it to `~/.config/copr`

## Submitting this package

```bash
# 1. Create a Copr project for the agent-stack libraries:
copr-cli create agent-stack \
    --description "Python libraries for the @mukundakatta agent-stack" \
    --instructions "dnf copr enable mukundakatta/agent-stack && dnf install python3-bedrock-ops" \
    --chroot fedora-rawhide-x86_64 \
    --chroot fedora-41-x86_64 \
    --chroot fedora-40-x86_64

# 2. Build the SRPM locally (or use COPR's "Custom Build"):
mock -r fedora-rawhide-x86_64 --buildsrpm \
    --spec packaging/copr/python-bedrock-ops.spec \
    --resultdir /tmp/srpm/

# 3. Upload + build:
copr-cli build agent-stack /tmp/srpm/python-bedrock-ops-0.1.0-1.fc41.src.rpm
```

Or skip the local SRPM step and have Copr build directly from the spec file via "Custom Build" in the web UI: <https://copr.fedorainfracloud.org/coprs/mukundakatta/agent-stack/add_build_custom/>

## After build succeeds

Users install via:

```bash
sudo dnf copr enable mukundakatta/agent-stack
sudo dnf install python3-bedrock-ops
```

## Updating

When the upstream library bumps version:

1. Bump `Version:` in the .spec
2. Add a `%changelog` entry
3. Run `copr-cli build agent-stack <new-srpm>` (or trigger a custom build via the web UI)
