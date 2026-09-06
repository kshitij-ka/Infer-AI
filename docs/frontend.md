# Frontend

This application provides two user-facing frontend pages served as static HTML/CSS/JavaScript, with no build tooling or framework dependencies. Both pages are served by the same FastAPI instance that provides the JSON API, mounted after all API routes so API endpoints retain priority.

## Routes and static assets

Two entry points are available:

- `/` -> `app/static/index.html`, the API reference and landing page. This is a static HTML document with no client side state, displaying documented endpoints with their request/response schemas, and a pill-nav navigation to jump between sections.

- `/console` -> `app/static/console.html`, the login and chat interface. This is a single-page application that manages login state, handles chat interactions, and displays system health via live polling.

- `/css/*` -> CSS stylesheets served from `app/static/css/`, currently `tokens.css` (design system variables) and `base.css` (reset, typography, component classes).

- `/js/*` -> JavaScript modules served from `app/static/js/`, currently `api.js` (HTTP client for login, chat, and health check) and `console.js` (console app state and event handlers).

Note that `/health` and `/metrics` remain API endpoints returning JSON/Prometheus text, not HTML pages. The API reference page's endpoint cards link to anchor IDs (`#endpoint-health`, `#endpoint-metrics`) on the same page; they do not fetch the live endpoints themselves.

## Why plain HTML/CSS/vanilla JavaScript

Adding a React/Vite/npm toolchain would introduce a second language runtime (Node.js), a build step, and hundreds of transitive npm packages for a scope that does not justify it. The application already ships as a single Python container with no external build services required; maintaining that simplicity is more valuable than adopting a framework that would primarily be used to manage state in a login form and a chat message list.

The console implements state and interactivity in vanilla JavaScript using event listeners on form elements and message containers, with fetch() for HTTP calls and DOM manipulation via `getElementById()`, `appendChild()`, and text node updates. This is intentionally minimal and readable; it is not a production-grade frontend codebase, but rather a demonstration that the API is usable from a browser without scaffolding.

## Design system

Both pages use the design tokens and component classes from `app/static/css/tokens.css` and `app/static/css/base.css`. The tokens are CSS custom properties (variables) defined in `tokens.css`, and every component class in `base.css` uses `var(--*)` references to these tokens rather than hardcoding color or size values.

The token set is derived from `UI Design/DESIGN.md`, the design language reference that specifies typography (Inter for body text, JetBrains Mono for code), a color palette (black `#111111` for primary CTAs, light gray `#f5f5f5` for surface cards, amber `#f59e0b` for warning states, red `#ef4444` for errors), and a border-radius scale (8px, 12px, 16px).

Not every token from DESIGN.md is represented in `tokens.css`; only those actually used by the two pages. For example, DESIGN.md specifies a complete spacing scale; `tokens.css` only defines the gaps and padding sizes that the mockups required. This keeps the token file maintainable and focused on what is shipped.

The component classes in `base.css` include button states (default, hover, active), input styling (text and password fields, disabled state), form error messages, message bubbles (user and assistant variants, error variant), badges, and status indicators (dot with text label for health check results). Each component is scoped to a class name (e.g., `.btn-primary`, `.btn-secondary`, `.chat-bubble`, `.chat-bubble-error`) and uses CSS classes rather than inline styles in the HTML.

## Mockup-vs-real-API reconciliation

The two design mockups (`UI Design/Backend Design UI.dc.html` and `UI Design/Answer Console.dc.html`) were created before the API implementation was complete, resulting in several discrepancies between the mockup's example responses and the actual API contract. The following were found and corrected:

### `/auth/login` response shape

**Mockup showed:** `{access_token, token_type, expires_in}`

**Real schema (`app/schemas/auth.py`):** `{access_token, token_type}`

The `expires_in` field does not exist in the real `LoginResponse` schema. This API returns only a bearer token with no expiration hint; the token's lifetime is configured server-side via JWT encoding, not communicated to the client in the login response. The API reference page was corrected to drop `expires_in` from the example response.

### `/health` response shape

**Mockup showed:** a flat structure `{status: "healthy"|"connected", redis, database}` with literal strings like "healthy" and "connected"

**Real implementation (`app/main.py`):** a nested structure `{status: "ok"|"degraded", checks: {database: "ok"|"error", redis: "ok"|"error"}}`

The real endpoint performs two independent health checks (database connectivity and Redis connectivity), represents each as "ok" or "error", and then summarizes the overall status as "ok" if both passed or "degraded" if any check failed. Both the API reference page and the console's System tab were corrected to reflect this nested shape and the actual status values.

### `/chat` response fields

**Mockup showed:** `{answer, latency_ms, prompt_tokens, completion_tokens, tokens_used, model}`

**Real schema (`app/schemas/chat.py`):** `{answer, latency_ms, prompt_tokens, completion_tokens}`

The real response omits both `tokens_used` (redundant given that `prompt_tokens` and `completion_tokens` are already returned) and `model` (not tracked per-request by the LLM client). The console's Chat tab was built to compute a token count display by summing `prompt_tokens + completion_tokens` and displaying it as "N tok" rather than storing a separate field.

### Retry badge and no server-exposed retry signal

**Mockup showed:** a "retried once" badge displayed alongside chat answers

**Real implementation:** the LLM client's `ask()` method in `app/services/llm_client.py` retries transient errors internally and returns a `ChatResponse` that contains no retry information at all; there is no way for the client to know whether the answer required a retry.

Rather than fabricate a retry signal in the frontend or add a new API field just to expose this information, the fabricated "retried once" badge was dropped entirely. If retry diagnostics are needed in the future, they would be exposed through structured logs or Prometheus metrics, not in the individual chat response.

### System tab health metrics

**Mockup showed:** uptime, requests/min, p95 latency, tokens-processed-today, error-rate, and a per-endpoint "200 OK" status list

**Real implementation:** the application exposes `/health` (reachable without authentication, returns {status, checks}) and `/metrics` (admin-only, returns Prometheus plain-text exposition format with counters and histograms for request outcomes, token usage, and latency).

The System tab mockup invented several metrics with no corresponding backend route. Rather than add a new JSON metrics summary endpoint (explicitly out of scope: the assessment asks for a JSON API, not an expansion of it), the System tab was built from only what is real:

1. A live poll of `GET /health` (every 10 seconds by default) that displays the overall status as a colored dot and lists the per-dependency checks (database, redis) with their individual statuses. This requires no authentication since `/health` is public.

2. For admin-role users only, a "View raw metrics" action that fetches `GET /metrics` using the stored bearer token (via `fetch(url, {headers: {Authorization: "Bearer " + token}})`) and opens the Prometheus text exposition format in a new tab via a Blob URL. This is necessary because a plain HTML `<a href>` cannot attach an Authorization header; a fetch call with credentials is required.

Non-admin users do not see the metrics action at all; the console does not show a control that will 403. This matches the backend's existing RBAC model rather than displaying a "forbidden" state in the UI.

## Authentication model in the console

The console stores the JWT in `sessionStorage` (not `localStorage`). Closing the browser tab clears the token and requires a fresh login on the next visit; this is a reasonable default for an API with no refresh token flow and avoids the larger security impact of `localStorage` persistence without adding complexity like a refresh-token rotation cycle.

The user's role (admin, user, or readonly) is determined by decoding the JWT payload client-side: the middle segment (between the two dots) is base64url-decoded to extract the JSON claims. No signature verification is performed, since this is the browser's own just-issued token with no possibility of forgery. There is no `/me` endpoint to ask the server for the current user's role, and none was added as part of this task.

### Logout, 401, and 429 handling

Logout clears the token from `sessionStorage` and returns the user to the login screen. This requires no API call; it is a client-side operation.

A 401 response from any authenticated endpoint (chat, System tab health check) clears the token and returns the user to the login screen. This ensures that an expired or revoked token does not leave the user in a broken state where all subsequent requests fail with 401.

A 429 (rate limit) response surfaces the server's actual rate-limit message in the response body as an inline warning banner above the chat input, rather than showing a generic error dialog. This provides more actionable feedback to the user about why they cannot send another message.

## App name: "Infer AI"

Both frontend pages use "Infer AI" as the application name and wordmark. The API reference page mockup already said "Infer AI"; the console mockup said "Answer". Per explicit instruction, "Infer AI" was standardized everywhere: the `<title>` tag in both pages, the wordmark text displayed to the user, the default `Settings.app_name` in `app/core/config.py`, and the `APP_NAME` environment variable in `.env.example`. There is no second brand name "Answer" alive anywhere in the codebase.

## What is out of scope

This task does not add new backend endpoints. The System tab does not fabricate metrics or call a metrics summary API that does not exist; it uses only the real `/health` and `/metrics` endpoints that already exist. There is no password reset flow, no user self-registration page, no metrics-export endpoint; these are consistent with the existing API design and the assessment's stated scope.

The authentication model remains a single short-lived JWT with no refresh token. The frontend does not change or extend this; it simply uses the existing `/auth/login` and JWT bearer auth scheme.
