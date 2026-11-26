# Security

How ChhapaKhata protects a shop's data: the rate limits, the sign-in rules, the
rules for data, and a map of the threats with what stops each one. Where a rule
lives in code or config, the file is named.

The live site runs as **Cloudflare → Caddy (`deploy/Caddyfile.public`) → Django
(gunicorn) → PostgreSQL**, all on one server.

---

## 1. Rate limits

Counters are kept in a cache shared by all web workers (`CACHES`, a file cache in
`config/settings/base.py`), so three workers count as one and a restart doesn't
hand out fresh attempts. A request over a limit gets **HTTP 429** with a
`Retry-After` header; the app shows "Too many attempts. Please wait a moment and try
again."

| Limit | Rate | Counted per | Applies to | Where |
|---|---|---|---|---|
| Anonymous | 120 / minute | address | every API call before signing in | `DEFAULT_THROTTLE_RATES["anon"]` |
| Signed-in | 600 / minute | person | every API call | `["user"]` |
| Heavy work | 30 / minute | person (or address) | PDFs (bills, receipts, slips, tickets, quotations, previews), Excel/PDF exports, imports, data export, erase | `apps/core/throttling.py::HeavyThrottle` |
| Sign-in | 20 / minute | address | `POST /auth/login/` | `["login"]`, `LoginView` |
| Password change | 5 / minute | person | `POST /auth/change-password/` | `["password"]`, `ChangePasswordView` |
| Back up now | 5 / hour | person | `POST /system/backups/run/` (a full database dump) | `BackupThrottle` |
| Sign-in lock-out | 5 failures → 15 min | username **and** address | wrong passwords | django-axes, see §2 |

Sizes are capped too:

| What | Cap | Where |
|---|---|---|
| Any request body | 12 MB | Caddy `request_body max_size` |
| Import file (Excel/ODS/CSV) | 10 MB, zip-bomb guarded | `apps/system/views.py`, `sheets.py` |
| Logo, stamp, signature image | 2 MB | `apps/core/serializers.py::MAX_IMAGE_BYTES` |

The price preview on the order form (called on every keystroke) is deliberately
**not** "heavy"; it only counts towards the 600/minute limit.

### The visitor's real address

Behind Cloudflare every request reaches the server from a Cloudflare machine. If
Django used that address, one attacker could lock the owner out (everyone would
share one address), and an attacker could get fresh attempts by switching
Cloudflare data centres. So:

1. Caddy trusts `CF-Connecting-IP` **only from Cloudflare's published ranges**
   (`trusted_proxies` in `Caddyfile.public`) and passes the result on as
   `X-Real-IP`.
2. `apps/core/client_ip.py::RealClientIPMiddleware` believes `X-Real-IP` only when
   the request came from the private Docker network or loopback (i.e. from Caddy).
   Sent straight to Django from the internet, the header is ignored.
3. django-axes and DRF read only `REMOTE_ADDR` (`AXES_IPWARE_META_PRECEDENCE_ORDER`,
   `NUM_PROXIES: 0`), so neither can be fooled by a forged `X-Forwarded-For`.

Cloudflare's ranges change rarely; check them against
<https://www.cloudflare.com/ips/> once or twice a year.

---

## 2. Sign-in rules

| Rule | Value |
|---|---|
| Password storage | Argon2 (`PASSWORD_HASHERS`) |
| Password strength | at least 8 characters; not a common password; not all digits; not similar to the username or name |
| Lock-out | 5 wrong passwords for the same username from the same address → that pair is locked for 15 minutes; a correct sign-in resets the count |
| Other addresses during a lock-out | still allowed, so an attacker can't lock the real staff out |
| Session | server-side session cookie, **12 hours sliding** (renewed while in use) |
| Cookies | `HttpOnly` session; `SameSite=Lax`; `Secure` when `SECURE_COOKIES=true` (set on the live site) |
| CSRF | required on every change; the SPA sends `X-CSRFToken` |
| On sign-in | the session id is replaced (no session fixation); the sign-in is written to the activity log with the address |
| Disabled accounts | refused, even with the right password; a disabled **business** refuses all its logins |
| Password change | needs the current password; every other signed-in device is signed out, the one that changed it stays in (`update_session_auth_hash`) |
| Active users | capped per business (`MAX_ACTIVE_USERS`, default 5); there is always one active owner |
| Roles | fixed matrix: owner, front desk, operator (see `docs/rbac.md`); every API view checks its permission on the server |

---

## 3. Security rules (headers and transport)

Set by Caddy on the live site (`deploy/Caddyfile.public`):

| Header / rule | Value | Stops |
|---|---|---|
| HTTPS | Cloudflare → Caddy, HTTP redirected | eavesdropping |
| `Strict-Transport-Security` | 1 year | downgrade to HTTP |
| `Content-Security-Policy` | `default-src 'self'`, scripts only from the site, no inline scripts, `frame-ancestors 'none'`, `form-action 'self'` | injected scripts (XSS) running, data sent to other sites |
| `X-Frame-Options` | `DENY` | clickjacking |
| `X-Content-Type-Options` | `nosniff` | uploaded files treated as scripts |
| `Referrer-Policy` | `same-origin` | order/customer ids leaking in links |
| `Permissions-Policy` | camera, mic, location off | misuse of the device |
| `/media/private/*` | 404 from Caddy | logos, stamps and signatures only through the signed-in app |
| Caddy admin API | off | reconfiguring the proxy |

The CSP was checked on 22 screens in Chrome and iPhone Safari (including opening
a PDF) with nothing blocked.

The shop-computer configs (`Caddyfile`, `Caddyfile.http`) leave HSTS off on
purpose: they use a local certificate, and HSTS would lock out a device that
can't trust it.

---

## 4. Data rules

- **Each business sees only its own data.** PostgreSQL Row-Level Security on every
  shop table refuses other businesses' rows, whatever the Python code asks for
  (`docs/adr/0008-multi-business-rls.md`). The app connects as a role that cannot
  bypass it.
- **Money records are append-only.** Ledger entries are never edited or deleted;
  a mistake is corrected by a reversing entry (`docs/adr/0004-append-only-ledgers.md`).
  Bill and receipt numbers are gap-free per fiscal year.
- **History.** Customers, orders, bills, payments and settings keep a change
  history (who, when, what), and the activity log records sign-ins, sign-outs and
  important actions with the address.
- **Prices are worked out on the server**, never trusted from the browser
  (`docs/adr/0005-server-side-pricing.md`).
- **Uploads.** Images only (checked by opening them), 2 MB each; imports 10 MB.
  Uploaded files are served only to signed-in users of the same business.
- **Deleting.** Bills and payments are cancelled, never deleted. "Erase all data"
  is owner-only, shows what will go first, needs a fresh backup and the word
  "Confirm" typed in, and is rate-limited; staff accounts, settings and the
  activity log are kept.
- **Backups.** Nightly and on demand: database dump, uploaded images and a
  SHA-256 checksum; 14 daily / 8 weekly / 12 monthly kept. The online copy is
  encrypted with rclone crypt before it leaves the server
  (`docs/backup-restore.md`).
- **Secrets** (`deploy/.env`, the server key, rclone config, backups) never go into
  git.

---

## 5. Threat map

| # | Threat (STRIDE) | Target | What stops it | Left over |
|---|---|---|---|---|
| T1 | Password guessing on the sign-in page (**S**poofing) | staff accounts | Argon2; 5 failures → 15-min lock per username + address; 20 sign-ins/min per address; password rules | a weak password still falls to a slow, patient guesser — see O1 |
| T2 | Locking the owner out by failing on purpose (**D**enial of service) | the shop's work | lock-out keyed on the attacker's real address, not Cloudflare's | none known |
| T3 | Forging `X-Forwarded-For` / `X-Real-IP` to dodge limits | rate limits, lock-out | Caddy trusts only Cloudflare ranges; Django trusts only Caddy | Cloudflare range list must stay current |
| T4 | Stolen session cookie (**S**poofing) | an open session | `HttpOnly`, `Secure`, `SameSite=Lax`, HTTPS + HSTS, CSP, 12 h expiry | a shared or unlocked shop PC — sign out at the end of the day |
| T5 | Cross-site request forgery (**T**ampering) | orders, payments | CSRF token on every change; `SameSite=Lax` | none known |
| T6 | Injected script (XSS) (**T**ampering / **I**nfo disclosure) | everything the user can see | React escapes output; CSP blocks inline and outside scripts | none known |
| T7 | One business reading another's data (**I**nfo disclosure) | customers, money | PostgreSQL RLS, app role without bypass; isolation tests | none known |
| T8 | A front-desk or operator user going beyond their role (**E**levation) | prices, money, users, settings | server-side permission check on every view; owner-only salary, backups, users | the owner account is all-powerful — see O1 |
| T9 | Changing or hiding money records (**T**ampering / **R**epudiation) | ledger, bills | append-only ledger, reversals only, gap-free numbers, change history, activity log | a database superuser on the server can still change rows — keep SSH access to the owner |
| T10 | Flooding the server with PDF/Excel requests (**D**enial of service) | a small EC2/Lightsail box | heavy limit 30/min, general limits, Cloudflare in front | a large distributed attack needs Cloudflare's "Under attack" mode |
| T11 | Huge or malicious uploads (**D**enial of service / **T**ampering) | disk, workers | 12 MB body cap; 2 MB images opened and checked; 10 MB imports with zip-bomb guard | none known |
| T12 | Reaching private images by URL (**I**nfo disclosure) | stamp, signature | `/media/private/*` blocked at Caddy; served via the app only | none known |
| T13 | Brute force on `/django-admin/` (**S**poofing) | superuser | same axes lock-out and limits; only superusers can use it | it is public; could be limited to the owner's address |
| T14 | Losing data (disk failure, ransomware, mistake) | everything | nightly + on-demand backups, checksums, encrypted online copy that is never deleted by sync | restore is only proven if it is practised — see O3 |
| T15 | Leaked secrets (key file, `.env`, backups in git) (**I**nfo disclosure) | server, database | `.gitignore`; secrets only on the server | the person holding the `.pem` key holds the server |
| T16 | Outdated packages with known holes | server | pinned versions, CI | update dependencies every few months |

---

## 6. Actions for the operator

| | Action | When |
|---|---|---|
| O1 | Change the live owner password to a long, unique one (a passphrase) | when the shop agrees — **not done yet, on hold** |
| O2 | After pulling this change, run `deploy/scripts/update.sh` so the web image is rebuilt with the new Caddyfile | next deploy |
| O3 | Practise a restore from a backup on a spare machine | twice a year |
| O4 | Check Cloudflare's IP ranges (<https://www.cloudflare.com/ips/>) against `Caddyfile.public` | twice a year |
| O5 | Optionally restrict `/django-admin/` to the owner's address in Caddy | if it is never used from elsewhere |
| O6 | Keep the `.pem` key and rclone crypt password off shared machines; write the crypt password on paper | always |
