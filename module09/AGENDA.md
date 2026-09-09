# Module 09 — Agenda

- bcrypt password hashing with passlib; only the hash is stored
- HS256 JWTs: `sub`, `scope`, `exp`, one symmetric `SECRET_KEY`
- A signed token is not an encrypted one
- `get_current_user` as a dependency; `/docs` grows a padlock
- The OAuth2 password flow: form-urlencoded, and the `username` field name
- One error message for an unknown address and a wrong password
- `401` with `WWW-Authenticate: Bearer` (RFC 6750)
- `UserOut` without `hashed_password`, so no response can leak it
- Why no cookie means the browser needs JavaScript
- Bearer tokens cannot be revoked; no logout endpoint, short expiry
- Per-user likes keyed on `current_user.id`
- Composite primary key + `ON DELETE CASCADE` on the join table
- `joinedload` mandatory under `AsyncSession`; `expire_on_commit=False`
- `bcrypt<4.1` pinned, and the passlib self-test that forces it
