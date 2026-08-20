# Module 03 — HTTP by hand with `http.server`

Two servers written against Python's standard library and nothing else: no Flask, no Django, no
`pip install`. The point is to meet HTTP with nothing done for you — you write the status line, you
pick the `Content-Type`, you count the bytes of the body — so that later, when a framework does all
of it invisibly, you know what it is doing.

| # | Folder | New idea | Python |
| --- | --- | --- | --- |
| 0 | [clock-server/](clock-server/) | The smallest handler that answers a browser: one method, one file | 18 lines |
| 1 | [blog-server/](blog-server/) | Routing, static files, a JSON API, a form POST, a real 404 | ~185 lines |

Read them in that order. `clock-server/` is the whole protocol in four statements; `blog-server/`
is what those four statements grow into once you need more than one URL.

---

## Prerequisites

```bash
python3 --version          # 3.12+ ; this doc was checked against 3.12.13
```

No dependencies to install. `pyproject.toml` exists only so the folder is a project like every
other folder in this repo — `dependencies = []` is the honest answer.

```bash
cd clock-server && python3 main.py     # → http://localhost:8001
cd blog-server  && python3 main.py     # → http://localhost:8001
```

Both bind **port 8001**, so run one at a time. `Address already in use` means the other one (or a
previous run you never stopped) still holds the socket. `Ctrl+C` stops the server; on macOS,
`lsof -ti:8001 | xargs kill` clears a stray one.

> **Run from inside the folder.** `clock-server/main.py` opens `clock.html` by a *relative* path,
> so it only works when the working directory is `clock-server/`. `blog-server/` deliberately does
> the opposite — see [`BASE_DIR`](#bases-and-paths).

---

## How `http.server` is put together

`HTTPServer` owns the socket. `BaseHTTPRequestHandler` owns one request. You never instantiate the
handler yourself — you hand the **class** to the server and it does the instantiating:

```python
server = HTTPServer(("", 8001), HttpHandler)   # host, port — and the class, not an instance
server.serve_forever()
```

### The life of one request

1. `HTTPServer(("", 8001), HttpHandler)` binds the socket. `""` means *every* interface (so
   `localhost`, `127.0.0.1` and your LAN IP all reach it); `"localhost"` would restrict it to this
   machine.
2. `serve_forever()` blocks in an accept loop.
3. A connection arrives → the server **constructs a new `HttpHandler`** and, inside
   `BaseHTTPRequestHandler.handle_one_request()`, reads and parses the request.
4. The base class looks for a method named `"do_" + self.command` — `do_GET`, `do_POST`, `do_DELETE`.
   No such attribute → it answers **501 Unsupported method** on its own and your code never runs.
5. Your `do_*` method writes the response.

- **`HTTPServer` is single-threaded.** Requests are served strictly one after another, so one slow
  handler stalls every other tab. Swapping in `ThreadingHTTPServer` (same constructor) fixes the
  stalling and immediately introduces the race that `storage.py`'s read-modify-write has been
  quietly getting away with.

---

## What't out of the box

Everything the base class has already worked out by the time your `do_*` method is called.

| Member | Type | What it holds | In these examples |
| --- | --- | --- | --- |
| `self.command` | `str` | The HTTP verb, `"GET"` / `"POST"` / `"DELETE"` | Used implicitly — it is what picks `do_GET` |
| `self.path` | `str` | The **raw** request target, query string and all: `/api/posts?page=2` | `urlparse(self.path).path` in [main.py:26](blog-server/main.py#L26) |
| `self.headers` | `email.message.Message` | Parsed headers. Lookup is **case-insensitive** and returns `None` when absent | `self.headers.get("Content-Length")` in [main.py:137](blog-server/main.py#L137) |
| `self.rfile` | binary stream | The unread request **body**. Read *exactly* `Content-Length` bytes | `self.rfile.read(length)` in [main.py:138](blog-server/main.py#L138) |
| `self.wfile` | binary stream | The response body you write. **Bytes only** — `str` raises `TypeError` | `self.wfile.write(data)` in [main.py:174](blog-server/main.py#L174) |
| `self.request_version` | `str` | What the client said: `"HTTP/1.1"` | — |
| `self.requestline` | `str` | The first line verbatim: `"GET /blog HTTP/1.1"` | Appears in the access log |
| `self.client_address` | `(host, port)` | Who connected | — |
| `self.server` | `HTTPServer` | The server instance, for anything you attached to it | — |

`self.path` is **not** a path — it is a URL target. Treat it as one:

```python
path = urlparse(self.path).path      # "/api/posts?page=2"  →  "/api/posts"
```

Without that split, `/api/posts?page=2` misses a `path == "/api/posts"` test and falls through to
your 404 branch. This is the single most common bug in hand-rolled handlers.

### Reading a body: why the length matters

```python
length = int(self.headers.get("Content-Length") or 0)
raw = self.rfile.read(length)
```

`self.rfile.read()` with no argument reads **until the connection closes** — and a keep-alive
client is not going to close it, so the server hangs until the browser gives up. Always pass the
length. The `or 0` covers a request with no body at all, where the header is absent and
`int(None)` would raise.

---

## What you call

| Method | What it does |
| --- | --- |
| `send_response(code, message=None)` | Writes the status line (`HTTP/1.0 200 OK`) and *automatically* queues the `Server:` and `Date:` headers. Also logs the request line. |
| `send_header(name, value)` | Queues one header. Call it as many times as you need. Buffered — nothing reaches the socket yet. |
| `end_headers()` | Writes the queued headers plus the blank line that ends them, and flushes. **Required.** Forget it and the client waits forever. |
| `self.wfile.write(data)` | The body. Bytes. |
| `send_error(code, message=None, explain=None)` | Status + a generated HTML error page + `Connection: close`, all in one call. Convenient, ugly output — `blog-server/` serves its own `404.html` instead. |
| `send_response_only(code)` | Status line with **no** `Server`/`Date`. For 1xx responses and hand-built header sets. |
| `log_message(fmt, *args)` | Every access-log line funnels through here. Override it to silence or redirect the log. |
| `protocol_version` | Class attribute, `"HTTP/1.0"` by default — which is why every response above says `HTTP/1.0`. Set it to `"HTTP/1.1"` for keep-alive, and then a correct `Content-Length` on every response becomes mandatory. |

### The order is not negotiable

```python
self.send_response(200)                        # 1. status line
self.send_header("Content-type", "text/html")  # 2. headers, any number
self.end_headers()                             # 3. the blank line
self.wfile.write(b"<h1>hi</h1>")               # 4. body
```

Call `send_header` after `end_headers` and the header text lands *in the body*, where the browser
renders it as page content. Write to `wfile` before `end_headers` and the body is parsed as
headers. Neither raises — you just get a broken page, which is why `blog-server/` routes every
response through one funnel and never repeats this sequence by hand.

---

# Example 0 — [clock-server/](clock-server/)

An analogue CSS clock, served by the shortest handler that works. The whole server:

```python
from http.server import BaseHTTPRequestHandler, HTTPServer


class HTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):                                   # any GET, whatever the path
        self.send_response(200)                         # status line + Server + Date
        self.send_header("Content-type", "text/html")   # tell the browser to render, not download
        self.end_headers()                              # nothing is sent before this
        with open("clock.html", "rb") as f:             # "rb" — wfile takes bytes, not str
            self.wfile.write(f.read())


server = HTTPServer(("", 8001), HTTPHandler)            # bind; the class, not an instance

try:
    server.serve_forever()                              # blocks in the accept loop
except KeyboardInterrupt:
    server.server_close()                               # Ctrl+C → release the socket
```

Line by line:

| Line | Why it is there |
| --- | --- |
| `do_GET` | The name *is* the routing. `BaseHTTPRequestHandler` finds it by string lookup on `"do_" + self.command`. |
| `send_response(200)` | Without it there is no status line, and the client sees a malformed response. |
| `Content-type: text/html` | Drop it and browsers guess; guess wrong and you get a download prompt or raw markup on screen. |
| `end_headers()` | The empty line that separates headers from body. Skipping it is the classic "request hangs" bug. |
| `open(..., "rb")` | `wfile` is a binary stream. Text mode gives `str`, and `wfile.write(str)` is a `TypeError`. |
| `HTTPServer(("", 8001), HTTPHandler)` | Host + port tuple, then the handler **class**. |
| `except KeyboardInterrupt` | `serve_forever()` only ends by exception. `server_close()` releases the port so the next run can bind it. |

Try it:

```bash
cd clock-server && python3 main.py
curl -i http://localhost:8001/            # 200, the clock page
curl -i http://localhost:8001/anything    # 200, the same clock page
curl -i -X POST http://localhost:8001/    # 501 Unsupported method ('POST')
```

Notice what that proves:

- **There is no routing.** `do_GET` never looks at `self.path`, so `/`, `/favicon.ico` and
  `/nonsense` all return the clock. Routing is something *you* add.
- **No `Content-Length`.** It works only because `protocol_version` is `HTTP/1.0`, where closing
  the connection is how the body ends. Switch to `HTTP/1.1` and the browser waits for bytes that
  never come.
- **501 is free.** Verbs you did not implement are answered by the base class.
- **The file is read on every request.** Fine for a lesson; a real static server caches and sends
  `Last-Modified` / `ETag`.

**Exercises**

1. Return `404.html` for any path other than `/` — you will need `self.path` and a check.
2. Add `Content-Length` and set `protocol_version = "HTTP/1.1"`. Confirm with
   `curl -v` that the connection is now reused instead of closed.
3. Add `do_HEAD` that sends the same headers with no body. Compare `curl -I` before and after.
4. Move the clock's JavaScript into `assets/clock.js` and watch the page break: the browser asks
   for `/assets/clock.js` and this server hands it *HTML* with `Content-Type: text/html`. That
   failure is the reason `blog-server/` has a static-file branch.

---

# Example 1 — [blog-server/](blog-server/)

The same base class, now carrying a small social feed: server-rendered pages, a static asset tree,
a JSON API that reads and writes `data/posts.json`, and a form POST that answers with a redirect.

| File | Role |
| --- | --- |
| [main.py](blog-server/main.py) | The handler: routing, request parsing, response writing |
| [storage.py](blog-server/storage.py) | Load / save / find over the one JSON file |
| [utils.py](blog-server/utils.py) | `BASE_DIR`, timestamps, id generation, input trimming, the path-traversal guard |
| [data/posts.json](blog-server/data/posts.json) | The entire database |
| `index.html` `blog.html` `contact.html` `404.html` | The four pages |
| `assets/css` `assets/js` `assets/img` | Everything served by the static branch |

## The routes

| Method | Path | Handler | Answer |
| --- | --- | --- | --- |
| `GET` | `/` `/blog` `/contact` | `ROUTES` dict → `send_html_file` | `200` + HTML |
| `GET` | `/api/posts` | `load_posts()` → `send_json` | `200` + the feed as JSON |
| `GET` | anything else | `send_static_or_404` | `200` + the file, or `404` + `404.html` |
| `POST` | `/api/posts` | `create_post` | `201` + the new post |
| `POST` | `/api/posts/<id>/comments` | `create_comment` | `201` + the new comment |
| `POST` | `/api/posts/<id>/like` | `toggle_like` | `200` + `{"likes": n}` |
| `POST` | `/contact` | `handle_contact` | `302` → `/`, body logged to the console |
| `DELETE` | `/api/posts/<id>` | `do_DELETE` | `200` + `{"ok": true}` |
| *any other verb* | — | base class | `501` |

Checked against the running server:

```bash
curl -i  http://localhost:8001/api/posts
curl -i -X POST -H 'Content-Type: application/json' \
     -d '{"author":"You","text":"hello"}' http://localhost:8001/api/posts        # 201
curl -s -X POST -H 'Content-Type: application/json' \
     -d '{oops'  http://localhost:8001/api/posts                                 # {"error": "Invalid JSON body"}
curl -s -X POST -H 'Content-Type: application/json' \
     -d '[1,2]'  http://localhost:8001/api/posts                                 # {"error": "Expected a JSON object"}
curl -s -X POST -d '{"delta":1}' http://localhost:8001/api/posts/nope/like        # {"error": "No such post"}
curl -i -X DELETE http://localhost:8001/api/posts/p1755648000000                 # {"ok": true}
curl -i -X PUT    http://localhost:8001/api/posts                                # 501
```

## Routing, by hand

```python
ROUTES = {"/": "index.html", "/blog": "blog.html", "/contact": "contact.html"}

POST_RE     = re.compile(r"^/api/posts/(?P<id>[\w-]+)$")
COMMENTS_RE = re.compile(r"^/api/posts/(?P<id>[\w-]+)/comments$")
LIKE_RE     = re.compile(r"^/api/posts/(?P<id>[\w-]+)/like$")
```

Two kinds of route, because they need different tools:

- **Fixed paths** → a dict. A dict lookup is the cheapest possible match, and adding a page means
  adding one line ([main.py:12](blog-server/main.py#L12)).
- **Paths with an id in them** → a compiled regex with a **named group**, so the id comes back as
  `match["id"]` instead of a string slice. `[\w-]+` also acts as validation: an id containing `/`
  or `..` cannot match in the first place.

`do_POST` then dispatches with the walrus operator, which matches and binds in one condition
([main.py:35-47](blog-server/main.py#L35-L47)):

```python
def do_POST(self):
    path = urlparse(self.path).path                  # strip ?query before comparing

    if path == "/api/posts":
        self.create_post()
    elif match := COMMENTS_RE.match(path):           # assign *and* test
        self.create_comment(match["id"])
    elif match := LIKE_RE.match(path):
        self.toggle_like(match["id"])
    elif path == "/contact":
        self.handle_contact()
    else:
        self.send_json({"error": "Not found"}, 404)
```

Order matters: `COMMENTS_RE` and `LIKE_RE` are anchored with `^...$`, so they cannot overlap — but
drop the `$` and `/api/posts/p1/comments` starts matching `POST_RE` too. Anchor every route regex.

Note the else branch answers **JSON**, not HTML. A `fetch()` that hits a bad API path gets a
parseable error; `assets/js/app.js` reads exactly that `error` key
([app.js:95](blog-server/assets/js/app.js#L95)).

## The one place headers are written

Every response in the file goes through `send_bytes` ([main.py:169-174](blog-server/main.py#L169-L174)):

```python
def send_bytes(self, data, content_type, status=200):
    self.send_response(status)
    self.send_header("Content-type", content_type)
    self.send_header("Content-Length", str(len(data)))   # str — headers are text
    self.end_headers()
    self.wfile.write(data)
```

The four-step sequence appears **once** in the whole program. Everything else is a thin wrapper
over it, which is why no route can get the order wrong:

| Wrapper | Adds |
| --- | --- |
| `send_json(payload, status=200)` | `json.dumps(..., ensure_ascii=False).encode("utf-8")` + `application/json; charset=utf-8`. `ensure_ascii=False` keeps real UTF-8 in the body instead of `\uXXXX` escapes — which is why the charset must be declared. |
| `send_html_file(filename, status=200)` | Reads a page from `BASE_DIR` and labels it `text/html; charset=utf-8`. The `status` parameter is what lets `404.html` be served *with a 404*, instead of the 200-with-an-error-page that so many sites ship. |
| `send_static_or_404(path)` | The fallback branch: guard the path, guess the MIME type, or serve the 404 page. |

`Content-Length` is computed from the bytes, never from the string — `len("café")` is 4 but the
UTF-8 body is 5 bytes, and a wrong length truncates the response or hangs the client.

## Parsing a request body twice, two ways

The API speaks JSON; the contact form speaks form encoding. Both start the same way — length,
then read — and diverge at the parse.

**JSON** ([main.py:135-147](blog-server/main.py#L135-L147)) — one helper, used by all three
mutating endpoints, which answers 400 itself and returns `None` so the caller can bail:

```python
def read_json(self):
    length = int(self.headers.get("Content-Length") or 0)
    raw = self.rfile.read(length)
    try:
        body = json.loads(raw or b"{}")            # empty body → {} rather than an exception
    except json.JSONDecodeError:
        self.send_json({"error": "Invalid JSON body"}, 400)
        return None
    if not isinstance(body, dict):                 # valid JSON, wrong shape: [1,2] or "hi"
        self.send_json({"error": "Expected a JSON object"}, 400)
        return None
    return body
```

Hence the two-line preamble on every write endpoint:

```python
body = self.read_json()
if body is None:
    return              # the 400 has already gone out — do not send a second response
```

Sending two responses on one connection is a real failure mode here: `send_response` after
`end_headers` appends a second status line into the first response's body.

**Form encoding** ([main.py:125-132](blog-server/main.py#L125-L132)) — the classic HTML form path:

```python
def handle_contact(self):
    length = int(self.headers.get("Content-Length") or 0)
    raw = self.rfile.read(length).decode("utf-8")           # name=Ann&email=a%40b.c&message=hi
    print("[contact]", {k: v[0] for k, v in parse_qs(raw).items()})

    self.send_response(302)                                 # Found
    self.send_header("Location", "/")                       # meaningless without the 302
    self.end_headers()                                      # no body — a redirect has none
```

`parse_qs` returns `{"name": ["Ann"]}` — every value is a **list**, because `a=1&a=2` is legal.
The `v[0]` comprehension flattens it, and discards duplicates in the process.

The 302 is the *no-JavaScript* answer: submit the form with scripting off and the browser follows
`Location` back to the home page — a plain server-rendered flow. With scripting on,
[contact.js](blog-server/assets/js/contact.js) intercepts `submit`, sends the same body by `fetch`
(which follows the redirect transparently, so `res.ok` is true), and shows an inline confirmation.
One endpoint, both worlds.

## Serving files, and refusing the ones you must

`send_static_or_404` is where a hand-written server is most likely to become a security incident
([main.py:159-167](blog-server/main.py#L159-L167)):

```python
def send_static_or_404(self, path):
    target = BASE_DIR / path.lstrip("/")                      # "/assets/css/app.css" → BASE_DIR/assets/css/app.css

    if not is_inside(target, BASE_DIR) or not target.is_file():
        return self.send_html_file("404.html", 404)

    mime, _ = mimetypes.guess_type(target.name)
    self.send_bytes(target.read_bytes(), mime or "application/octet-stream")
```

- `lstrip("/")` is required: `BASE_DIR / "/etc/passwd"` in `pathlib` throws the base away entirely
  and yields `/etc/passwd`. An absolute right-hand side wins. Strip the slash and it becomes a
  child path.
- `is_inside` ([utils.py:23-25](blog-server/utils.py#L23-L25)) is the actual guard:

  ```python
  return target.resolve().is_relative_to(root.resolve())
  ```

  `.resolve()` collapses `..` and follows symlinks *before* the comparison, so
  `/../../etc/passwd` resolves outside `BASE_DIR` and is refused. Compare unresolved paths and the
  check passes while the read escapes. Browsers and `curl` normalise `..` away on their own, so
  this only fires against a client that does not — which is precisely the client you are worried
  about.
- `is_file()` before reading turns a directory or a missing file into a clean 404 rather than an
  `IsADirectoryError` traceback.
- `mimetypes.guess_type` maps the extension to a type — `.css` → `text/css`, `.png` →
  `image/png`. Get this wrong and browsers refuse the stylesheet. The
  `or "application/octet-stream"` fallback means "unknown bytes, download it".

Two limits worth seeing rather than being told:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8001/data/posts.json   # 200 — the database is public
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8001/api/posts/p1755648000000  # 404 — no GET route for one post
```

The whole folder is served, `data/` included; and `POST_RE` is only wired into `do_DELETE`, so
fetching a single post by id falls through to the static branch. Both are exercises below.

## Bases and paths

```python
BASE_DIR = Path(__file__).parent        # utils.py:6
```

`Path("404.html")` resolves against the **working directory**, so it breaks the moment the server
is started from anywhere but its own folder — the bug recorded in the seeded feed, and the reason
`clock-server/` must be run from inside `clock-server/`. `Path(__file__).parent` is anchored to the
*source file* and is correct from any cwd. Everything else derives from it:
`BASE_DIR / filename` for pages, `BASE_DIR / "data" / "posts.json"` for storage
([storage.py:7](blog-server/storage.py#L7)).

## Storage, and the honesty of a JSON file

[storage.py](blog-server/storage.py) is three functions: `load_posts`, `save_posts`, `find_post`.
Every request that touches data reads the whole file, mutates a Python list, and writes the whole
file back. `load_posts` swallows a missing or corrupt file and returns `[]` with a warning, so a
half-written JSON file degrades to an empty feed instead of a 500.

This is a teaching database, and its limits are the lesson:

- **Read-modify-write is not atomic.** Two concurrent likes can each read `4` and each write `5`.
  Single-threaded `HTTPServer` hides it by serialising requests — switch to
  `ThreadingHTTPServer` and the race is live.
- **`json.dump` is not atomic either.** Kill the process mid-write and the file is truncated.
  The real fix is write-to-temp-then-`os.replace`.
- **The whole file is rewritten per change.** Fine at two posts, hopeless at fifty thousand.

Input handling stays on the server side of the boundary. `clean(value, limit)`
([utils.py:18-20](blog-server/utils.py#L18-L20)) trims and caps every user string, and the caller
supplies the ceiling — 2000 for post text, 500 for a comment, 60 for a name. `maxlength` in the
HTML is a courtesy to the user; the server assumes nothing about it. Output escaping is the
frontend's job and it uses `textContent`, not `innerHTML`, for anything a user typed
([feed.js:77-78](blog-server/assets/js/feed.js#L77-L78)).


## When to stop doing this by hand

| | Bare `BaseHTTPRequestHandler` | `SimpleHTTPRequestHandler` | A framework (Flask/FastAPI) |
| --- | --- | --- | --- |
| Routing | `if`/`elif` you write | Filesystem paths only | Decorators, converters, names |
| Static files | You write it (~8 lines, plus the guard) | Built in, with `ETag` / ranges | Built in, or handed to nginx |
| Body parsing | `Content-Length` + `json.loads` by hand | — | Automatic, validated |
| Errors | You choose the page and the code | Generated HTML | Handlers per exception type |
| Templating | None | None | Jinja2 / equivalent |
| Concurrency | One request at a time | One request at a time | A real WSGI/ASGI server |
| Production | **No** — the stdlib docs say so outright | No | Yes, behind a proper server |

`http.server` exists to teach and to be a two-minute file server (`python3 -m http.server`). It
does not do TLS, hardening, or performance. Having written the routing, the length counting, the
MIME guessing and the traversal guard once by hand, the value of a framework stops being a claim
and becomes an amount of code you can point at.

---

