# Security policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| `0.x` (latest on `main`) | Yes |
| Older tags | Best effort |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report them privately via one of:

1. [GitHub Security Advisories](https://github.com/leonardoburbanov/navbe_ai/security/advisories/new) (preferred)
2. Email the maintainer listed in [`pyproject.toml`](pyproject.toml)

Include:

- A short description of the issue
- Steps to reproduce (or a proof of concept)
- Impact assessment (what an attacker could do)
- Whether you have a suggested fix

## What to expect

- Acknowledgement within **7 days** (best effort)
- A fix or mitigation plan for confirmed issues affecting the latest release
- Credit in the advisory if you want it (optional)

## Scope notes

Navbe is local-first. Reports involving:

- Secret leakage via MCP/API responses or logs
- Path traversal / arbitrary file write outside the data home
- Unsafe SQL execution beyond intended read-only destination queries
- Credential file exposure

…are especially valuable.

Out of scope: vulnerabilities in third-party dependencies that are already tracked by Dependabot (open a normal issue if Navbe mishandles an upgrade).
