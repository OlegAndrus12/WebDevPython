"use strict";

/* Auth is a bearer token in the Authorization header, not a cookie, so the
 * browser never attaches it on its own the way it would a cookie. This file
 * is everything that gap pushes to the client: holding the token, attaching
 * it to fetches, hydrating the navbar, and driving the login/register forms
 * and the like buttons -- none of which a plain <form method="post"> could
 * do, since a form can't set a custom header.
 */

const TOKEN_KEY = "cnn_token";

/* Matched verbatim against the 401 body from POST /api/auth/login. The server
 * side of this string is NOT_VERIFIED_DETAIL in news/routers/auth.py. */
const NOT_VERIFIED_DETAIL = "Email is not verified";

function getToken() {
    try {
        return localStorage.getItem(TOKEN_KEY);
    } catch {
        return null;
    }
}

function setToken(token) {
    try {
        localStorage.setItem(TOKEN_KEY, token);
    } catch {
        /* Private browsing, storage disabled, etc. -- the login still
           "worked", it just won't outlive this page. */
    }
}

function clearToken() {
    try {
        localStorage.removeItem(TOKEN_KEY);
    } catch {
        /* ignore */
    }
}

async function authFetch(url, options = {}) {
    const token = getToken();
    const headers = new Headers(options.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(url, { ...options, headers });
}

function showError(el, message) {
    if (!el) return;
    el.textContent = message;
    el.classList.remove("d-none");
}

/* Same two lines as showError -- kept separate only because the elements it
 * targets carry their own alert-success/status styling. */
function showMessage(el, message) {
    if (!el) return;
    el.textContent = message;
    el.classList.remove("d-none");
}

async function errorDetail(response) {
    try {
        const body = await response.json();
        return body.detail || `Request failed (${response.status})`;
    } catch {
        return `Request failed (${response.status})`;
    }
}

/* ---- navbar ------------------------------------------------------------ */

function navLink(href, label) {
    const item = document.createElement("li");
    item.className = "nav-item";
    const a = document.createElement("a");
    a.className = "nav-link";
    a.href = href;
    a.textContent = label;
    item.appendChild(a);
    return item;
}

function renderLoggedOutNav(nav) {
    nav.replaceChildren(navLink("/login", "Login"), navLink("/register", "Register"));
}

function renderLoggedInNav(nav, user) {
    const greeting = document.createElement("li");
    greeting.className = "nav-item";
    const span = document.createElement("span");
    span.className = "nav-link disabled";
    span.textContent = `Hi, ${user.username}`;
    greeting.appendChild(span);

    const logoutItem = document.createElement("li");
    logoutItem.className = "nav-item";
    const logoutBtn = document.createElement("button");
    logoutBtn.type = "button";
    logoutBtn.className = "btn btn-link nav-link";
    logoutBtn.textContent = "Log out";
    logoutBtn.addEventListener("click", () => {
        clearToken();
        window.location.href = "/";
    });
    logoutItem.appendChild(logoutBtn);

    nav.replaceChildren(greeting, navLink("/liked", "Liked"), logoutItem);
}

async function hydrateNav() {
    const nav = document.getElementById("auth-nav");
    if (!nav) return;

    if (!getToken()) {
        renderLoggedOutNav(nav);
        return;
    }

    const response = await authFetch("/api/auth/me");
    if (!response.ok) {
        clearToken();
        renderLoggedOutNav(nav);
        return;
    }
    renderLoggedInNav(nav, await response.json());
}

/* ---- login / register --------------------------------------------------- */

function setupLoginForm() {
    const form = document.getElementById("login-form");
    if (!form) return;
    const errorEl = document.getElementById("auth-error");

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorEl?.classList.add("d-none");

        // OAuth2PasswordRequestForm parses this as form-urlencoded, with the
        // login's field named "username" -- see login.html's comment.
        const body = new URLSearchParams();
        body.set("username", form.elements.username.value);
        body.set("password", form.elements.password.value);

        const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body,
        });

        if (!response.ok) {
            const detail = await errorDetail(response);
            showError(errorEl, detail);
            // Only for this one reason, and only echoing back the address the
            // user just typed: revealing it on a wrong password would turn the
            // login form into a way to mail arbitrary strangers.
            if (detail === NOT_VERIFIED_DETAIL) {
                const block = document.getElementById("resend-block");
                block?.classList.remove("d-none");
                const emailField = block?.querySelector("input[name=email]");
                if (emailField) emailField.value = form.elements.username.value;
            }
            return;
        }

        const { access_token: accessToken } = await response.json();
        setToken(accessToken);
        window.location.href = "/";
    });
}

function setupRegisterForm() {
    const form = document.getElementById("register-form");
    if (!form) return;
    const errorEl = document.getElementById("auth-error");

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorEl?.classList.add("d-none");

        const payload = {
            username: form.elements.username.value,
            email: form.elements.email.value,
            password: form.elements.password.value,
        };

        const response = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            showError(errorEl, await errorDetail(response));
            return;
        }

        // No redirect to /login: the account cannot log in yet. Hide the form
        // so the address can't be submitted twice into a 409.
        form.classList.add("d-none");
        showMessage(
            document.getElementById("auth-success"),
            `Account created. We sent a confirmation link to ${payload.email} -- ` +
                "click it to finish, then log in."
        );
    });
}

/* ---- email verification -------------------------------------------------- */

/* Shared by /verify-email and the login page's warning block. Both POST the
 * same endpoint, which answers identically for a registered and an unknown
 * address -- so this reports whatever came back and never branches on it. */
function setupResendForm() {
    const form = document.getElementById("resend-form");
    if (!form) return;
    const statusEl = document.getElementById("resend-status");

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = form.querySelector("button[type=submit]");
        if (button) button.disabled = true;

        const response = await fetch("/api/auth/request_email", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: form.elements.email.value }),
        });

        if (response.ok) {
            showMessage(statusEl, (await response.json()).message);
        } else {
            showMessage(statusEl, await errorDetail(response));
            if (button) button.disabled = false;
        }
    });
}

/* The landing page for the link in the verification email. */
async function setupVerifyPage() {
    const statusEl = document.getElementById("verify-status");
    if (!statusEl) return;

    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
        statusEl.textContent = "This link is missing its token.";
        document.getElementById("resend-block")?.classList.remove("d-none");
        return;
    }

    // No authFetch: confirming an address is what proves who you are here, so
    // this endpoint takes no bearer token -- the whole point is that it works
    // for someone who cannot log in yet.
    const response = await fetch(`/api/auth/confirmed_email/${encodeURIComponent(token)}`);

    if (!response.ok) {
        // 422 expired/malformed, 401 wrong scope, 400 no such user. A new link
        // is the fix for all of them, so they share one branch.
        statusEl.textContent = await errorDetail(response);
        document.getElementById("resend-block")?.classList.remove("d-none");
        return;
    }

    statusEl.textContent = (await response.json()).message;
    document.getElementById("verify-next")?.classList.remove("d-none");
}

/* ---- like buttons -------------------------------------------------------- */

function setLikeButtonState(button, liked) {
    button.classList.toggle("liked", liked);
    button.setAttribute("aria-pressed", String(liked));
    const glyph = button.querySelector("[aria-hidden]");
    if (glyph) glyph.textContent = liked ? "♥" : "♡";
    const label = button.querySelector(".like-label");
    if (label) label.textContent = liked ? "Liked" : "Like";
}

async function markLikedButtons() {
    const buttons = document.querySelectorAll(".like-btn");
    if (buttons.length === 0 || !getToken()) return;

    const response = await authFetch("/api/me/liked");
    if (!response.ok) return;

    const likedIds = new Set((await response.json()).map((article) => article.id));
    buttons.forEach((button) => {
        if (likedIds.has(Number(button.dataset.articleId))) {
            setLikeButtonState(button, true);
        }
    });
}

function setupLikeButtons() {
    document.querySelectorAll(".like-btn").forEach((button) => {
        button.addEventListener("click", async () => {
            if (!getToken()) {
                window.location.href = "/login";
                return;
            }

            const liked = button.classList.contains("liked");
            const response = await authFetch(`/api/articles/${button.dataset.articleId}/like`, {
                method: liked ? "DELETE" : "POST",
            });

            if (response.status === 401) {
                clearToken();
                window.location.href = "/login";
                return;
            }
            if (response.ok) setLikeButtonState(button, !liked);
        });
    });
}

/* ---- liked-articles page --------------------------------------------------- */

function buildLikedCard(article, onUnlike) {
    const col = document.createElement("div");
    col.className = "col";

    const card = document.createElement("article");
    card.className = "card news-card h-100";

    const link = document.createElement("a");
    link.href = `/article/${article.id}`;
    if (article.image_url) {
        link.className = "card-img-link";
        const img = document.createElement("img");
        img.src = article.image_url;
        img.className = "card-img-top";
        img.loading = "lazy";
        img.alt = "";
        link.appendChild(img);
    } else {
        link.className = "card-img-link card-img-placeholder";
        link.setAttribute("aria-hidden", "true");
        const span = document.createElement("span");
        span.textContent = "CNN";
        link.appendChild(span);
    }
    card.appendChild(link);

    const body = document.createElement("div");
    body.className = "card-body d-flex flex-column";

    const meta = document.createElement("div");
    meta.className = "card-meta mb-2";
    const badge = document.createElement("span");
    badge.className = "source-badge";
    badge.textContent = article.source.name;
    meta.appendChild(badge);

    // Already liked -- that's why it's on this page -- so the button starts
    // filled, and a click here means "remove from this list", not "toggle".
    const unlikeBtn = document.createElement("button");
    unlikeBtn.type = "button";
    unlikeBtn.className = "like-btn liked ms-auto";
    unlikeBtn.dataset.articleId = article.id;
    unlikeBtn.setAttribute("aria-label", "Remove from liked articles");
    const glyph = document.createElement("span");
    glyph.setAttribute("aria-hidden", "true");
    glyph.textContent = "♥";
    unlikeBtn.appendChild(glyph);
    unlikeBtn.addEventListener("click", () => onUnlike(article.id, col, unlikeBtn));
    meta.appendChild(unlikeBtn);

    body.appendChild(meta);

    const title = document.createElement("h3");
    title.className = "card-title h6";
    const titleLink = document.createElement("a");
    titleLink.href = `/article/${article.id}`;
    titleLink.textContent = article.title;
    title.appendChild(titleLink);
    body.appendChild(title);

    if (article.description) {
        const description = document.createElement("p");
        description.className = "card-text";
        description.textContent = article.description;
        body.appendChild(description);
    }

    card.appendChild(body);
    col.appendChild(card);
    return col;
}

async function loadLikedArticles() {
    const list = document.getElementById("liked-list");
    const status = document.getElementById("liked-status");
    if (!list) return;

    if (!getToken()) {
        window.location.href = "/login";
        return;
    }

    const response = await authFetch("/api/me/liked");
    if (response.status === 401) {
        clearToken();
        window.location.href = "/login";
        return;
    }
    if (!response.ok) {
        if (status) status.textContent = "Could not load liked articles.";
        return;
    }

    // Removing the card here, not toggling it back to outline in place, is
    // the point of this page: "liked" is exactly what's still in the list.
    async function unlikeFromList(articleId, col, button) {
        button.disabled = true;
        const unlikeResponse = await authFetch(`/api/articles/${articleId}/like`, {
            method: "DELETE",
        });

        if (unlikeResponse.status === 401) {
            clearToken();
            window.location.href = "/login";
            return;
        }
        if (!unlikeResponse.ok) {
            button.disabled = false;
            return;
        }

        col.remove();
        if (status && list.children.length === 0) status.textContent = "No liked articles yet.";
    }

    const articles = await response.json();
    if (status) status.textContent = articles.length ? "" : "No liked articles yet.";
    list.append(...articles.map((article) => buildLikedCard(article, unlikeFromList)));
}

/* ---- newsletter --------------------------------------------------------- */

function renderNewsletterForm(form, status, submit, subscribed) {
    status.textContent = subscribed
        ? "You are subscribed to the daily newsletter."
        : "Get the day's new stories by email.";
    submit.textContent = subscribed ? "Unsubscribe" : "Subscribe";
    submit.classList.toggle("btn-accent", !subscribed);
    submit.classList.toggle("btn-outline-secondary", subscribed);
    form.dataset.subscribed = subscribed ? "1" : "0";
    form.classList.remove("d-none");
}

async function setupNewsletterForm() {
    const form = document.getElementById("newsletter-form");
    if (!form) return;

    const status = document.getElementById("newsletter-status");
    const submit = document.getElementById("newsletter-submit");
    const feedback = document.getElementById("newsletter-feedback");

    /* Stays hidden for a visitor with no token: there is nothing they could do
       with it, and PUT /api/me/subscription needs the bearer header. */
    if (!getToken()) return;

    const me = await authFetch("/api/auth/me");
    if (!me.ok) return;
    const user = await me.json();
    renderNewsletterForm(form, status, submit, user.subscribed);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        feedback.classList.add("d-none");

        const subscribed = form.dataset.subscribed === "1";
        submit.disabled = true;
        /* One URL either way -- the body says which state to end up in. */
        const response = await authFetch("/api/me/subscription", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ subscribed: !subscribed }),
        });
        submit.disabled = false;

        if (!response.ok) {
            showError(feedback, await errorDetail(response));
            feedback.classList.replace("alert-success", "alert-danger");
            return;
        }

        renderNewsletterForm(form, status, submit, !subscribed);
        feedback.classList.replace("alert-danger", "alert-success");
        showMessage(
            feedback,
            subscribed ? "Unsubscribed." : "Subscribed. The next newsletter will include you."
        );
    });
}

/* ---- wire-up ------------------------------------------------------------ */

document.addEventListener("DOMContentLoaded", () => {
    hydrateNav();
    setupLoginForm();
    setupRegisterForm();
    setupVerifyPage();
    setupResendForm();
    setupLikeButtons();
    markLikedButtons();
    loadLikedArticles();
    setupNewsletterForm();
});
