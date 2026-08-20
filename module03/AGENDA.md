# Module 03 — Agenda

Two servers built on `http.server` and nothing else, so every part of an HTTP exchange is written by
hand at least once. `clock-server/` is the smallest handler that a browser will render — one
`do_GET`, four statements, no routing at all — and every limitation it has motivates the next
example. `blog-server/` is what those four statements become once one URL is not enough: a route
table, a static-file branch with a path-traversal guard, a JSON API that reads and writes a file on
disk, and a form POST answered with a redirect so the page still works with JavaScript off. The
module ends by naming what a framework would have done for you, in code you have already written.
Method-by-method walkthrough, curl recipes and the mistake list live in [README.md](README.md).

## Topics

### The `http.server` machinery
- **The two objects** — `HTTPServer` owns the socket, `BaseHTTPRequestHandler` owns one request;
  the server is handed the handler *class*, never an instance
- **The life of a request** — bind, accept, construct a handler, parse the request line and headers,
  look up `"do_" + command`, write, discard
- **Verb dispatch by name** — `do_GET` / `do_POST` / `do_DELETE`; a missing method is a free
  `501 Unsupported method`, which is also how you discover what you have not implemented
- **One instance per request** — why `self` is not a place to keep state, and why shared state ends
  up at module level or on disk
- **Single-threaded by default** — one slow handler stalls every other tab; `ThreadingHTTPServer` is
  a one-word swap that immediately exposes the races a serialised server was hiding

### Reading a request
- **`self.path` is a URL target, not a path** — `urlparse(self.path).path` before any comparison,
  or `?page=2` silently 404s
- **`self.headers`** — an `email.message.Message`: case-insensitive lookup, `None` when absent, and
  `int(... or 0)` for the length of a body that may not exist
- **`self.rfile`** — the body is left unread for you; `read()` with no argument waits for the client
  to close and hangs a keep-alive request, so always read exactly `Content-Length` bytes
- **Two body formats, two parsers** — `json.loads` for the API, `parse_qs` for
  `application/x-www-form-urlencoded`, where every value arrives as a list because `a=1&a=2` is legal
- **Validating shape, not just syntax** — valid JSON that is not an object (`[1,2]`, `"hi"`) is still
  a 400; the parse helper answers it and returns `None` so the caller bails without sending a second
  response
- **Also available** — `self.command`, `self.request_version`, `self.requestline`,
  `self.client_address`, `self.server`

### Writing a response
- **The order is not negotiable** — `send_response` → `send_header`* → `end_headers` →
  `wfile.write`; out of order there is no exception, just headers rendered as page content or a body
  parsed as headers
- **`send_response` does more than the status line** — it also queues `Server:` and `Date:` and logs
  the request; `send_response_only` when you want neither
- **`end_headers()` is mandatory** — the blank line that ends the header block, and the classic
  cause of "the request just hangs"
- **`wfile` takes bytes** — hence `open(..., "rb")`, `.encode("utf-8")`, and `TypeError` when you
  forget
- **`Content-Length` from bytes, never from the string** — `len("café")` is 4 and the body is 5,
  and a wrong length truncates or hangs
- **Content types** — `text/html` vs `application/json; charset=utf-8` vs
  `mimetypes.guess_type()` for assets, and what a browser does with a stylesheet served as HTML
- **`protocol_version`** — `HTTP/1.0` by default, which is why a body can end by closing the
  connection; `HTTP/1.1` buys keep-alive and makes an accurate length compulsory
- **Status codes as part of the design** — `201` with the created object as the body, `302` plus
  `Location` and no body, `404` served *with* the 404 page rather than a 200, `400` with a
  machine-readable `{"error": ...}`
- **`send_error` vs your own page** — the generated error page against `404.html`, and the
  `status` parameter that lets one helper serve both
- **`log_message`** — every access-log line funnels through one overridable method

### Routing by hand
- **A dict for fixed paths** — the cheapest match, one line per page
- **Compiled regexes for path parameters** — named groups so an id is `match["id"]`; `[\w-]+` as
  validation, since an id containing `/` or `..` cannot match; anchoring with `^...$` so
  `/posts/<id>` and `/posts/<id>/comments` stay distinct
- **The walrus operator in a dispatch chain** — `elif match := LIKE_RE.match(path)` matches and
  binds in one condition
- **Fallbacks that fit the caller** — HTML `404.html` for pages, `{"error": "Not found"}` for API
  paths, so a `fetch()` always gets something parseable

### Serving static files safely
- **`Path` joining bites** — `BASE_DIR / "/etc/passwd"` discards the base entirely; `lstrip("/")`
  first
- **The traversal guard** — `target.resolve().is_relative_to(root.resolve())`: resolve *before*
  comparing, because `..` and symlinks are what you are defending against, and browsers normalise
  `..` away so only a hostile client ever reaches this code
- **`is_file()` before reading** — a directory or a missing file becomes a 404, not a traceback
- **MIME guessing** — extension → type, with `application/octet-stream` as the "unknown bytes"
  fallback
- **What "serve the folder" actually exposes** — `GET /data/posts.json` returns the whole database,
  and the fix is an allowlist rather than a blocklist

### Paths, state and storage
- **`Path(__file__).parent` vs the working directory** — the `FileNotFoundError` that appears only
  when the server is started from somewhere else, and why `clock-server/` must be run from inside
  its own folder
- **A JSON file as the database** — load-all, mutate a list, save-all; a corrupt or missing file
  degrading to an empty feed instead of a 500
- **Where that breaks** — read-modify-write is not atomic and neither is `json.dump`; the lost
  update is invisible under `HTTPServer` and reproducible under `ThreadingHTTPServer`; the whole
  file is rewritten per change
- **Server-side input handling** — trimming and per-field length caps in the handler, because
  `maxlength` in the HTML is a courtesy to the user and not a constraint on the client

### Where this stops
- **`http.server` is not for production** — no TLS, no hardening, no concurrency worth the name;
  the standard library says so itself
- **What a framework replaces** — routing, body parsing and validation, error handlers, templating,
  static serving, a real WSGI/ASGI server — measured against the code in this module rather than
  claimed
