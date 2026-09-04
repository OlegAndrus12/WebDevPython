# Module 03 — Agenda

`clock-server/`, `blog-server/` — both built on `http.server` alone.

- **The `http.server` machinery** — `HTTPServer` vs. `BaseHTTPRequestHandler`, verb dispatch, threading
- **Reading a request** — `self.path`, headers, `rfile`, JSON vs. form bodies, validation
- **Writing a response** — header order, `Content-Length`, content types, status codes
- **Routing by hand** — dict routes, compiled regexes, walrus-operator dispatch, fallbacks
- **Serving static files safely** — path joining, traversal guard, MIME guessing
- **Paths, state and storage** — JSON file as a database, race conditions, input limits
- **Where this stops** — what a framework would replace
