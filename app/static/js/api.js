/**
 * Thin fetch wrapper for the Infer AI backend API.
 *
 * Shape: a single low-level `request(method, path, { body, token })`
 * helper that does the actual fetch, JSON encode/decode, and error
 * unwrapping. Every endpoint-specific function (login now; chat/health
 * in later tasks) is a thin call to `request`, so adding them later is
 * additive, no restructuring of this file needed.
 *
 * Exposed as a plain global `window.Api` object (no ES modules) so
 * console.html can load this with a plain <script> tag, matching the
 * rest of the static site's no-build-step approach.
 */
(function () {
  "use strict";

  /**
   * Low-level request helper shared by every endpoint function.
   *
   * @param {string} method - HTTP method, e.g. "GET" or "POST".
   * @param {string} path - API path, e.g. "/auth/login".
   * @param {Object} [options]
   * @param {Object} [options.body] - JSON-serializable request body.
   * @param {string} [options.token] - bearer token to send as
   *   `Authorization: Bearer <token>`, omitted if not provided.
   * @returns {Promise<any>} the parsed JSON response body.
   * @throws {Error} with `.message` set to the server's `detail`
   *   string (or a generic fallback) whenever the response is not ok,
   *   and `.status` set to the HTTP status code.
   */
  async function request(method, path, options) {
    var opts = options || {};
    var headers = { Accept: "application/json" };
    var fetchInit = { method: method, headers: headers };

    if (opts.body !== undefined) {
      headers["Content-Type"] = "application/json";
      fetchInit.body = JSON.stringify(opts.body);
    }
    if (opts.token) {
      headers["Authorization"] = "Bearer " + opts.token;
    }

    var response;
    try {
      response = await fetch(path, fetchInit);
    } catch (networkErr) {
      var offlineErr = new Error("Network error: unable to reach the server");
      offlineErr.status = 0;
      throw offlineErr;
    }

    var data = null;
    try {
      data = await response.json();
    } catch (parseErr) {
      data = null;
    }

    if (!response.ok) {
      var message =
        (data && typeof data.detail === "string" && data.detail) ||
        "Request failed with status " + response.status;
      var err = new Error(message);
      err.status = response.status;
      err.data = data;
      throw err;
    }

    return data;
  }

  /**
   * Logs in with a username and password.
   *
   * @param {string} username
   * @param {string} password
   * @returns {Promise<{access_token: string, token_type: string}>}
   * @throws {Error} on 401 (invalid credentials), 429 (rate limited),
   *   or any other non-2xx response; `.message` carries the server's
   *   `detail` text when present.
   */
  function login(username, password) {
    return request("POST", "/auth/login", {
      body: { username: username, password: password },
    });
  }

  /**
   * Asks a question of the chat endpoint.
   *
   * @param {string} question
   * @param {string} token - bearer token for Authorization.
   * @returns {Promise<{answer: string, latency_ms: number,
   *   prompt_tokens: number, completion_tokens: number}>}
   * @throws {Error} on 403 (readonly role), 429 (rate limited), or
   *   any other non-2xx/network failure; `.message` carries the
   *   server's `detail` text when present.
   */
  function chat(question, token) {
    return request("POST", "/chat", {
      body: { question: question },
      token: token,
    });
  }

  /**
   * Checks backend health. No auth required.
   *
   * @returns {Promise<{status: "ok"|"degraded",
   *   checks: {database: "ok"|"error", redis: "ok"|"error"}}>}
   * @throws {Error} on network failure (the route itself never returns
   *   a non-2xx status).
   */
  function health() {
    return request("GET", "/health");
  }

  /**
   * Fetches raw Prometheus metrics text. Admin-only on the backend
   * (403 for any other role); requires a bearer token.
   *
   * This deliberately does NOT go through `request()`, since that
   * helper's contract is JSON-only (it always calls `response.json()`).
   * `/metrics` responds with `text/plain` Prometheus exposition format,
   * so this is a small standalone fetch that mirrors `request()`'s
   * Authorization header handling and error unwrapping without forcing
   * a JSON parse.
   *
   * @param {string} token - bearer token for Authorization.
   * @returns {Promise<string>} the raw metrics text body.
   * @throws {Error} on 403 (non-admin), network failure, or any other
   *   non-2xx response; `.status` is set to the HTTP status code when
   *   available.
   */
  async function metricsText(token) {
    var headers = { Authorization: "Bearer " + token };
    var response;
    try {
      response = await fetch("/metrics", { method: "GET", headers: headers });
    } catch (networkErr) {
      var offlineErr = new Error("Network error: unable to reach the server");
      offlineErr.status = 0;
      throw offlineErr;
    }

    var text = await response.text();

    if (!response.ok) {
      var err = new Error("Request failed with status " + response.status);
      err.status = response.status;
      throw err;
    }

    return text;
  }

  window.Api = {
    request: request,
    login: login,
    chat: chat,
    health: health,
    metricsText: metricsText,
  };
})();
