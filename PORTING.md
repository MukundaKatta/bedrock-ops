# Porting status

Where bedrock-ops is published, where it's queued, and what's intentionally not happening.

## Current

| Channel | State | URL |
|---|---|---|
| GitHub Release | live | https://github.com/MukundaKatta/bedrock-ops/releases/tag/v0.1.0 |
| PyPI | live | https://pypi.org/project/bedrock-ops/0.1.0/ |
| conda-forge | recipe PR submitted | https://github.com/conda-forge/staged-recipes/pull/33281 |
| nixpkgs | derivation PR submitted | https://github.com/NixOS/nixpkgs/pull/518492 |
| Homebrew tap | formula PR submitted | https://github.com/MukundaKatta/homebrew-tools/pull/1 |
| MCP server | live on npm | https://www.npmjs.com/package/@mukundakatta/bedrock-ops-mcp |

Install:

```bash
pip install bedrock-ops
```

## Roadmap

These are realistic ports the library could grow into. Each is a separate effort, not a quick translation.

### Plausible

| Target | Why | Approx scope |
|---|---|---|
| **TypeScript port → npm** | AWS SDK for JavaScript has the same Bedrock pain (throttle codes, cache token telemetry, structured streaming gaps). Fits the [`@mukundakatta/agent-*`](https://www.npmjs.com/~mukundakatta) family | ~1-2 weeks |
| **Go port → pkg.go.dev** | AWS Go SDK is heavily used in Lambda and Bedrock-on-Fargate setups; same pain class at scale | ~1 week |

### Not planned

| Target | Why not |
|---|---|
| Java / Maven Central | LangChain4j and AWS Strands have started filling this; competing in their territory adds friction |
| Ruby / PHP / Perl / Haskell / OCaml | No real LLM-tooling community in these ecosystems |
| Conan / vcpkg | C/C++ only |
| Homebrew / APT / DNF / Pacman / Chocolatey | Library-only formulas are rejected; distro packages target end-user apps, not Python libs |
| Docker Hub / GHCR / Quay | Libraries don't ship as containers — the entire Python lib ecosystem (numpy, pandas, requests) doesn't bother |
| Helm / Artifact Hub | Wrong artifact type (helm charts) |

## How to contribute a port

If you want to start a port, open an issue on this repo with the target ecosystem and a sketch of the public API mapping. Coordinate before writing code so we don't duplicate work.

A port is its own repo with its own release cadence; it shouldn't live in this monorepo. Cross-link via README "sibling libraries" sections.
