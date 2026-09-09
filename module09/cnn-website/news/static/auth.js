"use strict";

/* Auth is a bearer token in the Authorization header, not a cookie, so the
 * browser never attaches it on its own the way it would a cookie. This file
 * is everything that gap pushes to the client: holding the token, attaching
 * it to fetches, hydrating the navbar, and driving the login/register forms
 * and the like buttons -- none of which a plain <form method="post"> could
 * do, since a form can't set a custom header.
 */

const TOKEN_KEY = "cnn_token";

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
            showError(errorEl, await errorDetail(response));
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

        // Nothing stands between registering and logging in -- no address to
        // confirm -- so send them to the login form with the account ready.
        window.location.href = "/login";
    });
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

/* ---- wire-up ------------------------------------------------------------ */

document.addEventListener("DOMContentLoaded", () => {
    hydrateNav();
    setupLoginForm();
    setupRegisterForm();
    setupLikeButtons();
    markLikedButtons();
    loadLikedArticles();
});
