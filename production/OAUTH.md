# OAuth / OIDC scaffolding

Scope for this phase: **wiring only**. Local username/password login keeps
working unchanged. No paid gating is attached to OAuth — that lands in Phase 3
together with the Razorpay integration.

The overlay does not ship a custom auth implementation. We delegate entirely
to Open WebUI's native OAuth/OIDC support and only pass environment variables
through `compose.yaml`.

## Prerequisites

| Variable                         | Required | Notes |
| -------------------------------- | -------- | ----- |
| `WEBUI_URL`                      | yes (for OAuth) | Externally reachable origin, no trailing slash. Open WebUI builds the OAuth `redirect_uri` from this. |
| `WEBUI_SECRET_KEY`               | yes      | MUST be stable across restarts. Rotating it invalidates every session and every persisted OAuth token. The value baked into `compose.yaml` today is suitable for the current single-host deployment. |
| `ENABLE_OAUTH_SIGNUP`            | optional | `true` lets first-time OAuth callers auto-register. Leave unset until you decide your invite policy. |
| `OAUTH_MERGE_ACCOUNTS_BY_EMAIL`  | optional | `true` links an OAuth identity to an existing local account with the same email. Only enable when you trust the IdP's email-verification guarantees. |
| `ENABLE_OAUTH_PERSISTENT_CONFIG` | optional | Default `false` in `compose.yaml`. When `true`, settings edited via the admin UI are persisted in the DB and env values become initial defaults only. Keep `false` during bring-up so env always wins. |

## Google (native provider)

Callback URL to register at Google Cloud Console:

```
<WEBUI_URL>/oauth/google/callback
```

Environment:

```bash
export WEBUI_URL="https://your-host.example"
export GOOGLE_CLIENT_ID="..."
export GOOGLE_CLIENT_SECRET="..."
# Optional. Common value:
export GOOGLE_OAUTH_AUTHORIZE_PARAMS="prompt=select_account"
# Recommended so RP-initiated logout works:
export OPENID_PROVIDER_URL="https://accounts.google.com/.well-known/openid-configuration"
```

## Generic OIDC (one provider at a time)

Callback URL — register exactly this at your IdP:

```
<WEBUI_URL>/oauth/oidc/callback
```

Environment:

```bash
export WEBUI_URL="https://your-host.example"
export OPENID_PROVIDER_URL="https://idp.example/.well-known/openid-configuration"
export OAUTH_CLIENT_ID="..."
export OAUTH_CLIENT_SECRET="..."
export OAUTH_PROVIDER_NAME="Your IdP"      # shown on the login button
export OAUTH_SCOPES="openid email profile" # default — override only if your IdP requires extras
export OPENID_REDIRECT_URI="https://your-host.example/oauth/oidc/callback"
```

Notes:

* Only **one** generic OIDC provider can be configured via `OPENID_PROVIDER_URL`.
  Google can be used in parallel via the native `GOOGLE_*` variables.
* Account merging across providers is governed by
  `OAUTH_MERGE_ACCOUNTS_BY_EMAIL`. Without it, two providers returning the
  same email will create two separate accounts.

## Compose interaction

`production/compose.yaml` passes every variable above through with
`${VAR:-}` so that an unset variable leaves the container env empty and
Open WebUI falls back to local password login. Nothing is hardcoded; no
secrets are committed.

## Out of scope

* No paid-access gating (see `ext_authz.has_access` — currently allows all
  authenticated users). Razorpay + plan enforcement is Phase 3.
* No token/cost ledger. Usage and cost are observed via the Open WebUI admin
  panel and the vendor portals (Azure / OpenAI), not from this overlay.
