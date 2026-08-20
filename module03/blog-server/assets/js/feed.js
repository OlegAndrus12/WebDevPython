/* ============================================================
   Feed — reads and writes through the JSON API in main.py.
   All state lives in data/posts.json on the server.
   ============================================================ */
(function () {
  "use strict";

  const { avatar, timeAgo, toast, api, autoGrow, esc, me, setMe } = window.App;

  const feed = document.getElementById("feed");
  const input = document.getElementById("composer-input");
  const submit = document.getElementById("composer-submit");
  const nameInput = document.getElementById("composer-name");

  // Which posts this browser has liked — the server only keeps the count.
  const LIKED_KEY = "pyblog.liked";
  const liked = new Set(JSON.parse(localStorage.getItem(LIKED_KEY) || "[]"));
  const rememberLikes = () => localStorage.setItem(LIKED_KEY, JSON.stringify([...liked]));

  let posts = [];

  /* ---------------------------------------------------------- loading */
  async function loadFeed() {
    feed.innerHTML = '<div class="card"><div class="state">Loading posts…</div></div>';
    try {
      posts = await api("GET", "/api/posts");
      render();
    } catch (err) {
      feed.innerHTML =
        '<div class="card"><div class="state">Could not load the feed: ' +
        esc(err.message) +
        "</div></div>";
    }
  }

  function render() {
    feed.textContent = "";
    if (!posts.length) {
      feed.innerHTML =
        '<div class="card"><div class="state">No posts yet — write the first one above.</div></div>';
      return;
    }
    posts.forEach((post) => feed.appendChild(renderPost(post)));
  }

  function renderPost(post) {
    const el = document.createElement("article");
    el.className = "card post";
    el.dataset.id = post.id;

    const isLiked = liked.has(post.id);
    const count = post.comments.length;

    el.innerHTML = `
      <div class="post__head">
        <div class="post__who">
          <div class="post__author"></div>
          <div class="post__time js-time">${timeAgo(post.time)}</div>
        </div>
        <button class="delete-btn js-delete" title="Delete post" aria-label="Delete post">×</button>
      </div>
      <div class="post__text"></div>
      <div class="post__actions">
        <button class="action js-like${isLiked ? " is-liked" : ""}">
          <span class="js-likes">${post.likes}</span> ${post.likes === 1 ? "like" : "likes"}
        </button>
        <button class="action js-toggle">${count} ${count === 1 ? "comment" : "comments"}</button>
      </div>
      <div class="comments js-comments">
        <div class="js-comment-list"></div>
        <form class="comment-form js-comment-form">
          <input type="text" placeholder="Write a comment…" aria-label="Comment" maxlength="500">
          <button class="btn btn--quiet" type="submit">Reply</button>
        </form>
      </div>`;

    el.querySelector(".post__author").textContent = post.author;
    el.querySelector(".post__text").textContent = post.text;
    el.querySelector(".post__head").prepend(avatar(post.author));
    el.querySelector(".comment-form").prepend(avatar(me(), true));

    renderComments(el, post);
    wire(el, post);
    return el;
  }

  function renderComments(el, post) {
    const list = el.querySelector(".js-comment-list");
    list.textContent = "";
    post.comments.forEach((c) => {
      const row = document.createElement("div");
      row.className = "comment";
      row.innerHTML = `
        <div class="comment__body">
          <strong></strong><span class="post__time">${timeAgo(c.time)}</span>
          <p></p>
        </div>`;
      row.querySelector("strong").textContent = c.author;
      row.querySelector("p").textContent = c.text;
      row.prepend(avatar(c.author, true));
      list.appendChild(row);
    });

    const n = post.comments.length;
    el.querySelector(".js-toggle").textContent = `${n} ${n === 1 ? "comment" : "comments"}`;
  }

  /* ------------------------------------------------------ interactions */
  function wire(el, post) {
    const box = el.querySelector(".js-comments");
    const likeBtn = el.querySelector(".js-like");

    likeBtn.addEventListener("click", async () => {
      const wasLiked = liked.has(post.id);
      const delta = wasLiked ? -1 : 1;

      // Optimistic — roll back if the server disagrees.
      wasLiked ? liked.delete(post.id) : liked.add(post.id);
      likeBtn.classList.toggle("is-liked", !wasLiked);
      paintLikes(el, post.likes + delta);

      try {
        const res = await api("POST", `/api/posts/${post.id}/like`, { delta });
        post.likes = res.likes;
        paintLikes(el, post.likes);
        rememberLikes();
      } catch (err) {
        wasLiked ? liked.add(post.id) : liked.delete(post.id);
        likeBtn.classList.toggle("is-liked", wasLiked);
        paintLikes(el, post.likes);
        toast("Could not save the like: " + err.message, "err");
      }
    });

    el.querySelector(".js-toggle").addEventListener("click", () => {
      box.classList.toggle("open");
      if (box.classList.contains("open")) box.querySelector("input").focus();
    });

    el.querySelector(".js-delete").addEventListener("click", async () => {
      if (!confirm("Delete this post?")) return;
      try {
        await api("DELETE", `/api/posts/${post.id}`);
        posts = posts.filter((p) => p.id !== post.id);
        render();
        toast("Post deleted");
      } catch (err) {
        toast("Could not delete: " + err.message, "err");
      }
    });

    el.querySelector(".js-comment-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const field = e.target.querySelector("input");
      const text = field.value.trim();
      if (!text) return;

      field.disabled = true;
      try {
        const comment = await api("POST", `/api/posts/${post.id}/comments`, {
          author: me(),
          text,
        });
        post.comments.push(comment);
        field.value = "";
        renderComments(el, post);
        box.classList.add("open");
      } catch (err) {
        toast("Could not post the comment: " + err.message, "err");
      } finally {
        field.disabled = false;
        field.focus();
      }
    });
  }

  function paintLikes(el, n) {
    el.querySelector(".js-likes").textContent = n;
    el.querySelector(".js-like").lastChild.textContent = ` ${n === 1 ? "like" : "likes"}`;
  }

  /* --------------------------------------------------------- composer */
  nameInput.value = me();
  nameInput.addEventListener("change", () => {
    const name = nameInput.value.trim() || "You";
    nameInput.value = name;
    setMe(name);
  });

  input.addEventListener("input", () => {
    autoGrow(input);
    submit.disabled = !input.value.trim();
  });

  input.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !submit.disabled) publish();
  });

  submit.addEventListener("click", publish);

  async function publish() {
    const text = input.value.trim();
    if (!text) return;

    submit.disabled = true;
    submit.textContent = "Posting…";
    try {
      const post = await api("POST", "/api/posts", { author: me(), text });
      posts.unshift(post);
      input.value = "";
      input.style.height = "auto";
      render();
      toast("Saved to data/posts.json");
    } catch (err) {
      toast("Could not publish: " + err.message, "err");
      submit.disabled = false;
    } finally {
      submit.textContent = "Post";
    }
  }

  /* keep relative timestamps honest */
  setInterval(() => {
    document.querySelectorAll(".post").forEach((el) => {
      const post = posts.find((p) => p.id === el.dataset.id);
      if (post) el.querySelector(".js-time").textContent = timeAgo(post.time);
    });
  }, 60000);

  loadFeed();
})();
