# Week 6 Write-up
Tip: To preview this markdown file
- On Mac, press `Command (⌘) + Shift + V`
- On Windows/Linux, press `Ctrl + Shift + V`

## Instructions

Fill out all of the `TODO`s in this file.

## Submission Details

Name: **TODO** \
SUNet ID: **TODO** \
Citations: Fixes implemented with Claude Code (Anthropic).

This assignment took me about **TODO** hours to do.


## Brief findings overview
Semgrep's `semgrep ci` scan of `week6/` reported findings in the **SAST (code)**
category, concentrated in the FastAPI backend (`backend/app/routers/notes.py`,
`backend/app/routers/action_items.py`, and `backend/app/main.py`). No live
secrets (Secrets) or vulnerable dependencies (SCA) required remediation for this
pass.

By severity:
- **Critical (5 findings, 3 distinct issues):** code injection via `eval()`, SQL
  injection via an f-string in a raw query, and SQL injection risk in
  user-controlled `ORDER BY` handling on the two list endpoints.
- **High (4 findings):** `subprocess` with `shell=True` (command injection),
  path traversal on a file-read endpoint, and dynamic `urllib` use (SSRF /
  `file://` read).
- **Medium (3 findings):** wildcard CORS, plus lower-confidence duplicates of the
  `eval` and `urllib` findings.

**False positives / noisy rules:** The `generic-sql-fastapi` findings on
`notes.py:33` and `action_items.py:33` fired on `db.execute(stmt...)` where the
statement is built with the SQLAlchemy ORM and values are already bound. The only
user-controlled part was the sort column selected via `getattr`, guarded by
`hasattr`. That guard is broad (it accepts any model attribute, not just
columns), so rather than dismiss the finding I tightened it to a real column
allowlist — this both removes residual risk and clears the finding.

---

## Fix #1
a. File and line(s)
> `backend/app/routers/notes.py:104` — `debug_eval` endpoint.

b. Rule/category Semgrep flagged
> `python.fastapi.code.tainted-code-stdlib-fastapi` (Critical) and
> `python.lang.security.audit.eval-detected` (Medium) — code injection.

c. Brief risk description
> The endpoint passed the untrusted `expr` query parameter straight to `eval()`.
> An attacker could execute arbitrary Python (e.g.
> `?expr=__import__('os').system('rm -rf /')`), i.e. full remote code execution.

d. Your change (short code diff or explanation, AI coding tool usage)
> Replaced `eval()` with `ast.literal_eval()`, which only parses Python literals
> (numbers, strings, tuples, lists, dicts, booleans, `None`) and returns HTTP 400
> on anything else.
> ```python
> # before
> result = str(eval(expr))  # noqa: S307
> # after
> try:
>     result = str(ast.literal_eval(expr))
> except (ValueError, SyntaxError) as exc:
>     raise HTTPException(status_code=400, detail=f"Invalid expression: {exc}")
> ```

e. Why this mitigates the issue
> `ast.literal_eval` never evaluates function calls, attribute access, or operators
> that could invoke code. Untrusted input can no longer reach a code-execution
> sink, so the injection vector is eliminated.

## Fix #2
a. File and line(s)
> `backend/app/routers/notes.py:71-80` — `unsafe_search` endpoint.

b. Rule/category Semgrep flagged
> `python.fastapi.db.sqlalchemy-fastapi` (Critical),
> `python.fastapi.db.generic-sql-fastapi` (Critical), and
> `python.sqlalchemy.security.audit.avoid-sqlalchemy-text` (High) — SQL injection.

c. Brief risk description
> The `q` parameter was interpolated directly into a raw SQL string
> (`... LIKE '%{q}%' ...`) passed to `text()`. An attacker could break out of the
> string literal to read, modify, or delete data (e.g. `q=' OR '1'='1`).

d. Your change (short code diff or explanation, AI coding tool usage)
> Switched from f-string interpolation to a bound parameter.
> ```python
> # before
> sql = text(f"... WHERE title LIKE '%{q}%' OR content LIKE '%{q}%' ...")
> rows = db.execute(sql).all()
> # after
> sql = text("... WHERE title LIKE :pattern OR content LIKE :pattern ...")
> rows = db.execute(sql, {"pattern": f"%{q}%"}).all()
> ```

e. Why this mitigates the issue
> The database driver binds `:pattern` as a value, not as SQL text, so user input
> can never alter the query structure. The `%` wildcards are part of the bound
> value, preserving the LIKE-search behavior.

## Fix #3
a. File and line(s)
> `backend/app/routers/notes.py:33` and `backend/app/routers/action_items.py:33`
> — the `list_notes` / `list_items` endpoints (sort handling above the flagged
> `db.execute` line).

b. Rule/category Semgrep flagged
> `python.fastapi.db.generic-sql-fastapi` (Critical) — SQL injection.

c. Brief risk description
> The user-supplied `sort` parameter selected an `ORDER BY` column via
> `getattr(Model, sort_field)`, guarded only by `hasattr`. `hasattr` accepts any
> attribute on the model (relationships, hybrids, methods), which is broader than
> intended and is the kind of dynamic query construction the rule warns about.

d. Your change (short code diff or explanation, AI coding tool usage)
> Replaced the `hasattr` guard with an explicit allowlist derived from the table's
> real columns.
> ```python
> # before
> if hasattr(Note, sort_field):
>     stmt = stmt.order_by(order_fn(getattr(Note, sort_field)))
> # after
> sortable = {c.name for c in Note.__table__.columns}
> if sort_field in sortable:
>     stmt = stmt.order_by(order_fn(getattr(Note, sort_field)))
> ```
> (Same change applied to `action_items.py` with `ActionItem`.)

e. Why this mitigates the issue
> Only genuine, sortable column names can reach `order_by`; any other value falls
> back to the safe default (`created_at DESC`). Combined with SQLAlchemy building
> the statement, no user input flows into raw SQL.

---

## Additional fixes (High / Medium)
Beyond the required three, I remediated the remaining High/Medium findings:

| # | File:line | Rule / category | Fix |
|---|-----------|-----------------|-----|
| 4 | `notes.py:112` (`debug_run`) | `subprocess-shell-true`, `tainted-os-command-*` (High) — command injection | Switched to `shell=False` with `shlex.split(cmd)` and a 5s timeout, so no shell interprets metacharacters (`;`, `|`, `` ` ``, `$()`). |
| 5 | `notes.py:128` (`debug_read`) | `tainted-path-traversal-stdlib-fastapi` (High) — path traversal | Resolve the requested path under a fixed `data/` base dir and reject anything that escapes it (`../../etc/passwd`). |
| 6 | `notes.py:120` (`debug_fetch`) | `dynamic-urllib-use-detected` (Medium) — SSRF / `file://` read | Reject any scheme other than `http`/`https` before calling `urlopen`, plus a timeout. |
| 7 | `notes.py:98` (`debug_hash_md5`) | weak hash (MD5) | Replaced MD5 with SHA-256. |
| 8 | `main.py:24` | `wildcard-cors` (Medium) — CORS misconfig | Replaced `allow_origins=["*"]` with an explicit origin allowlist (env-overridable via `CORS_ALLOW_ORIGINS`). |

**Residual risk / recommendation:** The `/debug/*` endpoints (`run`, `fetch`,
`read`) have no legitimate production purpose. The hardening above closes the
specific Semgrep findings, but `debug_run` can still execute allowed binaries and
`debug_fetch` can still reach internal HTTP hosts. The safest end state is to
delete these endpoints or gate them behind authentication and disable them
outside local development.

## Supply Chain (SCA) fixes
A separate `Supply Chain` scan (SCA, not SAST) flagged 16 findings — 1 High, 14
Medium, 1 Low — all in `requirements.txt`. Unlike the code findings above (which
flag insecure patterns in code we wrote and are keyed by Semgrep rule names),
these flag published **CVEs** in third-party packages and are keyed by CVE +
package version. The remediation is to upgrade the package, not edit code.

The pinned versions were years out of date and did not match what the app
actually runs on (the code and tests were written against pydantic 2 / FastAPI
0.121 / SQLAlchemy 2.0). I pinned `requirements.txt` to the current, patched
versions already installed and tested:

| Package | Before | After | Representative CVEs cleared |
|---------|--------|-------|----------------------------|
| Werkzeug | 0.14.1 | 3.1.3 | CVE-2024-34069, CVE-2024-49766, CVE-2023-23934 |
| Jinja2 | 2.10.1 | 3.1.6 | CVE-2020-28493, CVE-2024-22195, CVE-2024-34064, CVE-2024-56326, CVE-2025-27516 |
| requests | 2.19.1 | 2.32.5 | CVE-2023-32681, CVE-2024-35195, CVE-2024-47081 |
| pydantic | 1.5.1 | 2.11.10 | CVE-2021-29510, CVE-2024-3772 |
| fastapi | 0.65.2 | 0.121.3 | (kept in sync with pydantic 2 / starlette) |
| sqlalchemy | 1.3.23 | 2.0.39 | — |
| PyYAML | 5.1 | 6.0.2 | — |
| MarkupSafe | 1.1.0 | 3.0.2 | — |
| uvicorn | 0.11.8 | 0.38.0 | — |

**Reachability note:** most SCA findings were reported as "No Reachability
Analysis" / "Conditionally Reachable" (e.g. the Werkzeug debugger CSRF only
applies in dev/debug mode), with all EPSS scores Low (<4%) — lower real-world
risk than the confirmed, directly-reachable code findings above. A few findings
are future-dated CVEs (e.g. CVE-2026-27199); the packages are pinned to the
latest available releases, so any not-yet-patched upstream would need to be
triaged/accepted rather than fixed by a bump.

## Verification
- `python -c "import backend.app.main"` — imports cleanly.
- `python -m pytest backend -q` — **3 passed** (only pre-existing deprecation
  warnings remain).
- All `requirements.txt` pins verified to match the installed, tested versions.
