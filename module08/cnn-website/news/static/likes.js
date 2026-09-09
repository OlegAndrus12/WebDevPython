"use strict";

/* Likes in the browser, with no authentication anywhere.
 *
 * Every like route takes the reader's id in the path, so the client has to
 * decide which reader it is acting as. That choice is what the navbar picker
 * holds, and localStorage is where it survives a reload. It is a stand-in for
 * a session, not a security boundary: picking a different id in the dropdown
 * is exactly as allowed as picking your own, because nothing here proves
 * anything. Replacing this file with a real login is a later module's job.
 */

const USER_KEY = "cnn_user_id";

function getUserId() {
    try {
        const raw = localStorage.getItem(USER_KEY);
        return raw ? Number(raw) : null;
    } catch {
        return null;
    }
}

function setUserId(userId) {
    try {
        if (userId === null) localStorage.removeItem(USER_KEY);
        else localStorage.setItem(USER_KEY, String(userId));
    } catch {
        /* Private browsing, storage disabled -- the picker still works for
           this page, it just won't be remembered on the next one. */
    }
}

async function errorDetail(response) {
    try {
        const body = await response.json();
        return body.detail || `Request failed (${response.status})`;
    } catch {
        return `Request failed (${response.status})`;
    }
}

/* ---- the "acting as" picker --------------------------------------------- */

/* Populated from GET /api/users. A stored id that no longer exists -- the user
 * was deleted through the API -- is cleared rather than left selected, or every
 * like would 404 against a phantom. */
async function setupUserPicker() {
    const picker = document.getElementById("user-picker");
    if (!picker) return;

    const response = await fetch("/api/users");
    if (!response.ok) return;

    const users = await response.json();
    const stored = getUserId();
    const known = users.some((user) => user.id === stored);
    if (stored !== null && !known) setUserId(null);

    picker.replaceChildren();

    const none = document.createElement("option");
    none.value = "";
    none.textContent = users.length ? "reading as…" : "no readers yet";
    picker.appendChild(none);

    users.forEach((user) => {
        const option = document.createElement("option");
        option.value = String(user.id);
        option.textContent = user.username;
        if (user.id === stored && known) option.selected = true;
        picker.appendChild(option);
    });

    picker.addEventListener("change", () => {
        setUserId(picker.value ? Number(picker.value) : null);
        // Whose likes are shown depends on the answer, so re-render rather
        // than trying to patch the current view in place.
        window.location.reload();
    });
}

/* Shown instead of a like when nobody is picked. Not an alert(): the page is
 * perfectly usable for reading, only liking needs an identity. */
function warnNoUser() {
    const banner = document.getElementById("no-user-warning");
    if (banner) {
        banner.classList.remove("d-none");
        banner.scrollIntoView({ block: "nearest" });
    }
}

/* ---- like buttons -------------------------------------------------------- */

function setLikeButtonState(button, liked) {
    button.classList.toggle("liked", liked);
    button.setAttribute("aria-pressed", String(liked));
    const glyph = button.querySelector("[aria-hidden]");
    if (glyph) glyph.textContent = liked ? "♥" : "♡";
}

/* One request for the whole page, not one per card: the liked list is short
 * and a card grid would otherwise fire twelve GETs to colour twelve hearts. */
async function markLikedButtons() {
    const buttons = document.querySelectorAll(".like-btn");
    const userId = getUserId();
    if (buttons.length === 0 || userId === null) return;

    const response = await fetch(`/api/users/${userId}/liked`);
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
            const userId = getUserId();
            if (userId === null) {
                warnNoUser();
                return;
            }

            const liked = button.classList.contains("liked");
            button.disabled = true;
            const response = await fetch(
                `/api/users/${userId}/articles/${button.dataset.articleId}/like`,
                { method: liked ? "DELETE" : "POST" }
            );
            button.disabled = false;

            // Both directions are idempotent server-side, so the only failures
            // worth handling are a deleted user or a missing article.
            if (response.ok) setLikeButtonState(button, !liked);
        });
    });
}

/* ---- the liked-articles page --------------------------------------------- */

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

    // Everything on this page is liked by definition, so the heart starts
    // filled and a click means "take it off the list", not "toggle".
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

    const userId = getUserId();
    if (userId === null) {
        if (status) status.textContent = "Pick a reader in the navbar to see their likes.";
        return;
    }

    const response = await fetch(`/api/users/${userId}/liked`);
    if (!response.ok) {
        if (status) status.textContent = await errorDetail(response);
        return;
    }

    // Removing the card rather than emptying the heart in place is the point of
    // this page: what is still listed is exactly what is still liked.
    async function unlikeFromList(articleId, col, button) {
        button.disabled = true;
        const unlikeResponse = await fetch(
            `/api/users/${userId}/articles/${articleId}/like`,
            { method: "DELETE" }
        );
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

/* ---- wire-up ------------------------------------------------------------- */

document.addEventListener("DOMContentLoaded", () => {
    setupUserPicker();
    setupLikeButtons();
    markLikedButtons();
    loadLikedArticles();
});
