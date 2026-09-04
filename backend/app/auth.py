"""Demo-user identity — the ONLY seam in the codebase that decides "who is
the current user."

Phase 3 does not implement real authentication (per PRODUCT.md/RELIABILITY.md:
single JWT demo account, no multi-tenant RBAC needed at this scale, and
Phase 3's scope explicitly excludes real JWT). Every endpoint that needs the
current user's identity must depend on `get_current_user()` — never read a
user id off a request field, a header, or invent one inline in a route.

This is deliberate: when real JWT verification replaces this later, only
this function's body changes (decode the token, look up the user). No
endpoint logic, no watchlist-ownership checks, and no data model change is
required, because every call site already goes through this one dependency.

Watchlist endpoints still check `watchlist.user_id == current_user` against
this identity (see app/services/watchlist_access.py) — Phase 3 does not
pretend authorization doesn't exist just because authentication is stubbed.
"""

import uuid

DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def get_current_user() -> uuid.UUID:
    return DEMO_USER_ID
