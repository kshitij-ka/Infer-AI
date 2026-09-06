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

  window.Api = {
    request: request,
    login: login,
  };
})();
