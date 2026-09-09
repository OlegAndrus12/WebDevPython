# Module 08 — Agenda

- A second `APIRouter` with its own `prefix` and `tags`
- `POST` / `PATCH` / `DELETE` and their codes: 201, 204, 404, 409, 422
- Uniqueness checked in the app so a duplicate is a 409, not an IntegrityError
- `PATCH` semantics: optional fields + `model_dump(exclude_unset=True)`
- Why patching a row with its own value must not conflict
- `Path(..., ge=1)`: constrained path parameters
- A composite primary key as the integrity rule; idempotent like/unlike
- `ON DELETE CASCADE` on a join table
- Joining an association table and ordering by *its* column (`liked_at`)
- `joinedload` still mandatory under `AsyncSession`
- `EmailStr` and the `email-validator` extra; reserved-TLD rejections
- Identity without authentication: a `localStorage` picker as a stand-in
- Server-rendered shells filled by `fetch`
