/**
 * Infer AI console app logic.
 *
 * Replaces the design mockup's fake `DCLogic`/`Component` templating
 * framework with plain vanilla JS: a single mutable state object, a
 * `render()` function that rebuilds the DOM under #app from scratch
 * whenever state changes, and `setState()` to mutate + re-render. No
 * virtual DOM, no diffing, the console is small enough that a full
 * re-render on every state change is simple and fast enough.
 *
 * Loaded as a plain global script (no ES modules), after api.js, so it
 * reads `window.Api`.
 *
 * Scope for this task: login screen wired to real POST /auth/login,
 * token stored in sessionStorage, app shell with tab bar (Chat active
 * by default), sign out. Chat/System tab bodies are stub placeholders
 * only, Tasks 4 and 5 fill those in.
 */
(function () {
  "use strict";

  var SESSION_TOKEN_KEY = "inferai_token";
  var SESSION_USERNAME_KEY = "inferai_username";

  var state = {
    view: "login", // "login" | "app"
    tab: "chat", // "chat" | "system"
    username: "",
    token: null,
    loginError: null,
    loginPending: false,
  };

  function setState(patch) {
    Object.assign(state, patch);
    render();
  }

  function getInitials(username) {
    if (!username) return "";
    var parts = username
      .replace(/[._-]+/g, " ")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (parts.length === 0) return "";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }

  // ---- Element builder helper ----------------------------------------

  /**
   * Minimal hyperscript-style element builder: h(tag, attrs, children).
   * Keeps the render functions below readable without a build step.
   */
  function h(tag, attrs, children) {
    var el = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (key) {
      var value = attrs[key];
      if (value == null || value === false) return;
      if (key === "class") {
        el.className = value;
      } else if (key.indexOf("on") === 0 && typeof value === "function") {
        el.addEventListener(key.slice(2).toLowerCase(), value);
      } else if (key === "text") {
        el.textContent = value;
      } else {
        el.setAttribute(key, value === true ? "" : value);
      }
    });
    (children || []).forEach(function (child) {
      if (child == null) return;
      el.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    });
    return el;
  }

  // ---- Login screen ----------------------------------------------------

  function renderLoginScreen() {
    var usernameInput = h("input", {
      class: "text-input",
      type: "text",
      id: "login-username",
      placeholder: "jane.doe",
      required: true,
      autocomplete: "username",
    });
    usernameInput.style.marginBottom = "16px";

    var passwordInput = h("input", {
      class: "text-input",
      type: "password",
      id: "login-password",
      placeholder: "••••••••",
      required: true,
      autocomplete: "current-password",
    });
    passwordInput.style.marginBottom = "8px";

    var errorNode = null;
    if (state.loginError) {
      errorNode = h("div", { class: "login-error", text: state.loginError });
    }

    var submitLabel = state.loginPending ? "Signing in…" : "Sign in";
    var submitButton = h("button", {
      class: "btn-primary",
      type: "submit",
      style: "width:100%;",
      disabled: state.loginPending,
      text: submitLabel,
    });

    var form = h(
      "form",
      {
        class: "login-card",
        onSubmit: function (e) {
          e.preventDefault();
          handleLogin(usernameInput.value.trim(), passwordInput.value);
        },
      },
      [
        h("div", { class: "login-brand" }, [
          h("div", { class: "login-brand-mark" }),
          h("span", { class: "login-brand-name", text: "Infer AI" }),
        ]),
        h("div", { class: "login-subtitle", text: "Sign in to the AI Q&A console" }),
        h("label", { class: "login-label", for: "login-username", text: "Username" }),
        usernameInput,
        h("label", { class: "login-label", for: "login-password", text: "Password" }),
        passwordInput,
        errorNode,
        h("div", { style: "margin-top:16px;" }, [submitButton]),
        h("div", { class: "mono small login-caption", text: "POST /auth/login" }),
      ]
    );

    return h("div", { class: "login-screen" }, [form]);
  }

  async function handleLogin(username, password) {
    setState({ loginError: null });
    if (!username || !password) {
      setState({ loginError: "Username and password are required" });
      return;
    }
    setState({ loginPending: true, loginError: null });
    try {
      var result = await window.Api.login(username, password);
      sessionStorage.setItem(SESSION_TOKEN_KEY, result.access_token);
      sessionStorage.setItem(SESSION_USERNAME_KEY, username);
      setState({
        view: "app",
        tab: "chat",
        username: username,
        token: result.access_token,
        loginPending: false,
        loginError: null,
      });
    } catch (err) {
      setState({
        loginPending: false,
        loginError: err.message || "Sign in failed, please try again",
      });
    }
  }

  // ---- App shell ---------------------------------------------------------

  function renderTopNav() {
    var chatPill = h("button", {
      class: "nav-pill" + (state.tab === "chat" ? " active" : ""),
      type: "button",
      text: "Chat",
      onClick: function () {
        setState({ tab: "chat" });
      },
    });
    var systemPill = h("button", {
      class: "nav-pill" + (state.tab === "system" ? " active" : ""),
      type: "button",
      text: "System",
      onClick: function () {
        setState({ tab: "system" });
      },
    });

    return h("div", { class: "app-topnav" }, [
      h("div", { class: "app-topnav-brand" }, [
        h("div", { class: "app-topnav-mark" }),
        h("span", { class: "app-topnav-name", text: "Infer AI" }),
      ]),
      h("div", { class: "nav-pill-group" }, [chatPill, systemPill]),
      h("div", { class: "app-topnav-user" }, [
        h("div", { class: "app-avatar", text: getInitials(state.username) }),
        h("button", {
          class: "app-signout",
          type: "button",
          text: "Sign out",
          onClick: handleSignOut,
        }),
      ]),
    ]);
  }

  function renderAuthCaption() {
    return h("div", {
      class: "mono small app-auth-caption",
      text: "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9…redacted",
    });
  }

  function renderTabBody() {
    if (state.tab === "chat") {
      return h("div", { class: "tab-body-stub", id: "chat-tab-root" }, [
        h("p", { text: "Chat tab (coming in a later task)." }),
      ]);
    }
    return h("div", { class: "tab-body-stub", id: "system-tab-root" }, [
      h("p", { text: "System tab (coming in a later task)." }),
    ]);
  }

  function renderAppShell() {
    return h("div", { class: "app-shell" }, [
      renderTopNav(),
      renderAuthCaption(),
      renderTabBody(),
    ]);
  }

  function handleSignOut() {
    sessionStorage.removeItem(SESSION_TOKEN_KEY);
    sessionStorage.removeItem(SESSION_USERNAME_KEY);
    setState({
      view: "login",
      tab: "chat",
      username: "",
      token: null,
      loginError: null,
      loginPending: false,
    });
  }

  // ---- Root render -------------------------------------------------------

  function render() {
    var root = document.getElementById("app");
    root.innerHTML = "";
    root.appendChild(state.view === "login" ? renderLoginScreen() : renderAppShell());
  }

  function init() {
    var storedToken = sessionStorage.getItem(SESSION_TOKEN_KEY);
    var storedUsername = sessionStorage.getItem(SESSION_USERNAME_KEY);
    if (storedToken && storedUsername) {
      state.view = "app";
      state.token = storedToken;
      state.username = storedUsername;
    }
    render();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
