"""A small blog served by http.server — routing, static files and a JSON API."""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import mimetypes
import re

from storage import load_posts, save_posts, find_post
from utils import BASE_DIR, clean, is_inside, new_id, now_ms

ROUTES = {
    "/": "index.html",
    "/blog": "blog.html",
    "/contact": "contact.html",
}

POST_RE = re.compile(r"^/api/posts/(?P<id>[\w-]+)$")
COMMENTS_RE = re.compile(r"^/api/posts/(?P<id>[\w-]+)/comments$")
LIKE_RE = re.compile(r"^/api/posts/(?P<id>[\w-]+)/like$")


class HttpHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ROUTES:
            self.send_html_file(ROUTES[path])
        elif path == "/api/posts":
            self.send_json(load_posts())
        else:
            self.send_static_or_404(path)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/posts":
            self.create_post()
        elif match := COMMENTS_RE.match(path):
            self.create_comment(match["id"])
        elif match := LIKE_RE.match(path):
            self.toggle_like(match["id"])
        elif path == "/contact":
            self.handle_contact()
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_DELETE(self):
        match = POST_RE.match(urlparse(self.path).path)
        if not match:
            return self.send_json({"error": "Not found"}, 404)

        posts = load_posts()
        remaining = [p for p in posts if p["id"] != match["id"]]
        if len(remaining) == len(posts):
            return self.send_json({"error": "No such post"}, 404)

        save_posts(remaining)
        self.send_json({"ok": True})

    # ----------------------------------------------------------- API verbs
    def create_post(self):
        body = self.read_json()
        if body is None:
            return

        text = clean(body.get("text"), 2000)
        if not text:
            return self.send_json({"error": "Post text is required"}, 400)

        post = {
            "id": new_id(),
            "author": clean(body.get("author"), 60) or "Anonymous",
            "text": text,
            "time": now_ms(),
            "likes": 0,
            "comments": [],
        }

        posts = load_posts()
        posts.insert(0, post)
        save_posts(posts)
        self.send_json(post, 201)

    def create_comment(self, post_id):
        body = self.read_json()
        if body is None:
            return

        text = clean(body.get("text"), 500)
        if not text:
            return self.send_json({"error": "Comment text is required"}, 400)

        posts = load_posts()
        post = find_post(posts, post_id)
        if post is None:
            return self.send_json({"error": "No such post"}, 404)

        comment = {
            "author": clean(body.get("author"), 60) or "Anonymous",
            "text": text,
            "time": now_ms(),
        }
        post.setdefault("comments", []).append(comment)
        save_posts(posts)
        self.send_json(comment, 201)

    def toggle_like(self, post_id):
        body = self.read_json()
        if body is None:
            return

        delta = 1 if body.get("delta", 1) >= 0 else -1

        posts = load_posts()
        post = find_post(posts, post_id)
        if post is None:
            return self.send_json({"error": "No such post"}, 404)

        post["likes"] = max(0, post.get("likes", 0) + delta)
        save_posts(posts)
        self.send_json({"likes": post["likes"]})

    def handle_contact(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        print("[contact]", {k: v[0] for k, v in parse_qs(raw).items()})

        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()


    def read_json(self):
        """Parse a JSON request body, answering 400 on bad input."""
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self.send_json({"error": "Invalid JSON body"}, 400)
            return None
        if not isinstance(body, dict):
            self.send_json({"error": "Expected a JSON object"}, 400)
            return None
        return body

    def send_json(self, payload, status=200):
        self.send_bytes(
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

    def send_html_file(self, filename, status=200):
        self.send_bytes((BASE_DIR / filename).read_bytes(), "text/html; charset=utf-8", status)

    def send_static_or_404(self, path):
        """Serve a file from BASE_DIR, refusing anything that escapes it."""
        target = BASE_DIR / path.lstrip("/")

        if not is_inside(target, BASE_DIR) or not target.is_file():
            return self.send_html_file("404.html", 404)

        mime, _ = mimetypes.guess_type(target.name)
        self.send_bytes(target.read_bytes(), mime or "application/octet-stream")

    def send_bytes(self, data, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    server = HTTPServer(("", 8001), HttpHandler)
    print("Serving on http://localhost:8001 (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBye")
    finally:
        server.server_close()
