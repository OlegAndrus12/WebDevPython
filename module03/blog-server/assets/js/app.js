/* ============================================================
   Shared helpers: theme, avatars, time, toasts, fetch wrapper.
   ============================================================ */
(function () {
  "use strict";

  const THEME_KEY = "pyblog.theme";
  const NAME_KEY = "pyblog.name";

  /* ---------- theme ---------- */
  const saved = localStorage.getItem(THEME_KEY);
  const dark = saved || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  applyTheme(dark);

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.querySelectorAll("[data-theme-toggle]").forEach((b) => {
      b.textContent = theme === "dark" ? "☀" : "☾";
      b.title = theme === "dark" ? "Light mode" : "Dark mode";
    });
  }

  document.addEventListener("click", (e) => {
    if (!e.target.closest("[data-theme-toggle]")) return;
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
  });

  /* ---------- identity (whoever is posting from this browser) ---------- */
  function me() {
    return localStorage.getItem(NAME_KEY) || "You";
  }
  function setMe(name) {
    localStorage.setItem(NAME_KEY, name);
  }

  /* ---------- avatars ---------- */
  const COLORS = ["#5b7c99", "#8a7a68", "#6b8f71", "#8f6b7a", "#7a6b8f", "#996b5b"];

  function hash(str) {
    let h = 0;
    for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0;
    return Math.abs(h);
  }

  function avatar(name, small) {
    const el = document.createElement("div");
    el.className = "avatar" + (small ? " avatar--sm" : "");
    el.style.background = COLORS[hash(name) % COLORS.length];
    el.textContent = name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
    el.setAttribute("aria-label", name);
    return el;
  }

  /* ---------- time ---------- */
  function timeAgo(ts) {
    const secs = Math.max(1, Math.floor((Date.now() - ts) / 1000));
    if (secs < 60) return "just now";
    const mins = Math.floor(secs / 60);
    if (mins < 60) return mins + "m ago";
    const hours = Math.floor(mins / 60);
    if (hours < 24) return hours + "h ago";
    const days = Math.floor(hours / 24);
    if (days < 7) return days + "d ago";
    return new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  /* ---------- toasts ---------- */
  function toast(message, kind) {
    let host = document.querySelector(".toasts");
    if (!host) {
      host = document.createElement("div");
      host.className = "toasts";
      document.body.appendChild(host);
    }
    const el = document.createElement("div");
    el.className = "toast" + (kind ? " toast--" + kind : "");
    el.textContent = message;
    host.appendChild(el);
    setTimeout(() => {
      el.classList.add("out");
      el.addEventListener("animationend", () => el.remove());
    }, 2400);
  }

  /* ---------- JSON fetch ---------- */
  async function api(method, url, body) {
    const res = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const payload = res.status === 204 ? null : await res.json().catch(() => null);
    if (!res.ok) throw new Error((payload && payload.error) || "HTTP " + res.status);
    return payload;
  }

  function autoGrow(el) {
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
  }

  function esc(str) {
    return String(str).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  document.addEventListener("DOMContentLoaded", () => {
    const path = location.pathname.replace(/\/$/, "") || "/";
    document.querySelectorAll(".tab").forEach((tab) => {
      const href = tab.getAttribute("href").replace(/\/$/, "") || "/";
      tab.classList.toggle("active", href === path);
    });
    document.querySelectorAll("[data-avatar]").forEach((slot) => {
      slot.replaceWith(avatar(slot.dataset.avatar, slot.hasAttribute("data-small")));
    });
  });

  window.App = { avatar, timeAgo, toast, api, autoGrow, esc, me, setMe };
})();
