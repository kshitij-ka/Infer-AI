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
 * Scope: login screen wired to real POST /auth/login, token stored in
 * sessionStorage, app shell with tab bar (Chat active by default),
 * sign out. Chat tab is wired to real POST /chat (message list,
 * loading state, 429/403/generic error handling). System tab body is
 * still a stub placeholder, Task 5 fills it in.
 */
(function () {
  "use strict";

  var SESSION_TOKEN_KEY = "inferai_token";
  var SESSION_USERNAME_KEY = "inferai_username";

  var GREETING_MESSAGE = {
    role: "assistant",
    text: "Hi, I'm ready to answer questions. Ask me anything.",
  };

  var state = {
    view: "login", // "login" | "app"
    tab: "chat", // "chat" | "system"
    username: "",
    token: null,
    loginError: null,
    loginPending: false,
    chatMessages: [GREETING_MESSAGE],
    chatInput: "",
    chatSending: false,
    chatWarning: null, // inline warning banner text (e.g. 429 rate limit)
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
      return renderChatTab();
    }
    return h("div", { class: "tab-body-stub", id: "system-tab-root" }, [
      h("p", { text: "System tab (coming in a later task)." }),
    ]);
  }

  // ---- Chat tab ----------------------------------------------------------

  function renderChatMessage(m) {
    if (m.role === "user") {
      return h("div", { class: "chat-row chat-row-user" }, [
        h("div", { class: "chat-bubble chat-bubble-user", text: m.text }),
      ]);
    }

    var bubbleClass = "chat-bubble chat-bubble-assistant";
    if (m.variant === "error") {
      bubbleClass += " chat-bubble-error";
    } else if (m.variant === "system") {
      bubbleClass += " chat-bubble-system";
    }

    var children = [h("div", { class: bubbleClass, text: m.text })];

    if (m.hasMeta) {
      children.push(
        h("div", { class: "chat-meta-row" }, [
          h("span", { class: "mono chat-meta-item", text: m.latencyMs + "ms" }),
          h("span", { class: "mono chat-meta-item", text: m.tokens + " tok" }),
        ])
      );
    }

    return h("div", { class: "chat-row chat-row-assistant" }, [
      h("div", { class: "chat-bubble-col" }, children),
    ]);
  }

  function renderChatTab() {
    var messageNodes = state.chatMessages.map(renderChatMessage);

    if (state.chatSending) {
      messageNodes.push(
        h("div", { class: "chat-row chat-row-assistant" }, [
          h("div", { class: "chat-bubble chat-bubble-assistant chat-bubble-thinking", text: "Thinking…" }),
        ])
      );
    }

    var warningNode = null;
    if (state.chatWarning) {
      warningNode = h("div", { class: "chat-warning-banner", text: state.chatWarning });
    }

    var chatInput = h("input", {
      class: "text-input",
      type: "text",
      id: "chat-input",
      placeholder: "Ask a question…",
      value: state.chatInput,
      disabled: state.chatSending,
      onInput: function (e) {
        state.chatInput = e.target.value;
      },
    });
    chatInput.value = state.chatInput;

    var sendButton = h("button", {
      class: "btn-primary chat-send-btn",
      type: "submit",
      disabled: state.chatSending,
      text: state.chatSending ? "Sending…" : "Send",
    });

    var form = h(
      "form",
      {
        class: "chat-input-row",
        onSubmit: function (e) {
          e.preventDefault();
          handleSendMessage(chatInput.value);
        },
      },
      [
        h("div", { class: "chat-input-row-inner" }, [warningNode, h("div", { class: "chat-input-fields" }, [chatInput, sendButton])]),
      ]
    );

    return h("div", { class: "chat-tab-root", id: "chat-tab-root" }, [
      h("div", { class: "chat-scroll" }, [h("div", { class: "chat-scroll-inner" }, messageNodes)]),
      form,
    ]);
  }

  async function handleSendMessage(rawText) {
    var text = rawText.trim();
    if (!text || state.chatSending) return;

    var token = state.token;
    var newMessages = state.chatMessages.concat([{ role: "user", text: text }]);
    setState({ chatMessages: newMessages, chatInput: "", chatSending: true, chatWarning: null });

    try {
      var result = await window.Api.chat(text, token);
      var totalTokens = (result.prompt_tokens || 0) + (result.completion_tokens || 0);
      var assistantMsg = {
        role: "assistant",
        text: result.answer,
        hasMeta: true,
        latencyMs: Math.round(result.latency_ms),
        tokens: totalTokens,
      };
      setState({
        chatMessages: state.chatMessages.concat([assistantMsg]),
        chatSending: false,
      });
    } catch (err) {
      if (err.status === 429) {
        setState({
          chatSending: false,
          chatInput: text,
          chatWarning: err.message || "Rate limit exceeded, please slow down",
        });
        return;
      }

      if (err.status === 403) {
        setState({
          chatMessages: state.chatMessages.concat([
            {
              role: "assistant",
              variant: "system",
              text: err.message || "This account cannot use the chat API.",
            },
          ]),
          chatSending: false,
        });
        return;
      }

      setState({
        chatMessages: state.chatMessages.concat([
          {
            role: "assistant",
            variant: "error",
            text: err.message || "Something went wrong while contacting the chat API.",
          },
        ]),
        chatSending: false,
      });
    }
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
      chatMessages: [GREETING_MESSAGE],
      chatInput: "",
      chatSending: false,
      chatWarning: null,
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
