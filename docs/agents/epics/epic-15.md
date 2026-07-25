# EPIC 15 — GitHub App auth for sync

**Status:** done  
**Goal:** Migrate sync auth from classic OAuth App + `repo` scope to the Navbe AI **GitHub App** via Device Flow user tokens, with refresh-token handling and fine-grained app permissions — no client secret in the CLI.  
**Non-goal:** Web OAuth callback; embedding client secret; JWT/installation-only tokens; secrets domain rework; workspace layout changes.

## Why

GitHub recommends GitHub Apps over OAuth Apps. EPIC 14 shipped OAuth App Device Flow as the quick path. Navbe AI already exists as a GitHub App (`Iv23livr6YIrrz0WNGpN`).

## Depends on

- **EPIC 14** — Device Flow CLI/MCP surfaces + workspace sync

## Design

- Same UX: `navbe login github`, `auth_github_*`
- User-to-server tokens (`ghu_` / `ghr_`); no `scope=repo`
- Default public Client ID for Navbe AI; override via `NAVBE_GITHUB_APP_CLIENT_ID`
- Legacy `NAVBE_GITHUB_OAUTH_CLIENT_ID` still read as fallback
- Refresh when access token near expiry (no client secret for device-flow refresh)
- Status may include `install_url` when the app is not installed

### GitHub App settings (operators)

1. Enable **Device Flow**
2. Keep user-to-server token expiration opted in
3. Permissions: Metadata (R), Contents (R/W), Administration (R/W)
4. Install on user/org that owns workspace repos

## Definition of Done

- [x] Login works against Navbe AI GitHub App Client ID (default or env)
- [x] No OAuth App / `repo` scope; no client secret in CLI
- [x] Expired access tokens refresh via `refresh_token` before sync ops
- [x] Missing install yields a clear install URL in status/errors
- [x] Docs + guards green
