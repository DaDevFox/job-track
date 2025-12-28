Concrete architecture (data flow)

Local service (FastAPI) — single local server (only listens on localhost):

/api/jobs — job records (title, company, location, description, apply_link, scraped_at, tags, is_applied, applied_date, profile_used)

/api/profiles — profiles with personal info + resume metadata; endpoints to upload new PDFs or version them

/api/scrape — triggers a scrape job or returns results from the scraper queue

DB: SQLite + migrations (alembic optional). PDFs stored under ~/.local/simplify/resumes/<profile>/<version>.pdf and reference in DB.

Scraper (Playwright) — a small worker process started by the local service:

Use site-specific extractor rules (CSS/XPath) or generic site heuristics for job title/location/description + link. Playwright can render JS pages and extract reliably. 
PromptCloud

Extension (TypeScript) — content scripts + popup/options page:

Shows profiles from local server (fetch from localhost API) — user picks profile.

On job page, fills text fields (name/email/phone/etc.). Opens local server endpoint to get selected resume metadata. For file upload: show instructions to the user (open file picker) or trigger a local helper via native messaging if you need automation beyond browser limits.

When user clicks “Apply (go to company site)”, extension sends a pendingApply record to local server (so the app knows you opened the link). When user returns, extension or TUI will ask: “Did you apply?” and mark it applied with date/profile. If the extension can detect the page’s form submit event before navigation, it can auto-mark applied — but that depends on the target site. (Simpler: show a confirm dialog when user returns.) 
Google Groups
+1

TUI (Textual) — job list, filters (new-grad only), quick-open link (open in browser), keyboard navigation with vim-like shortcuts, filter/persisted saved searches, review applied jobs with profile + resume version.

Minimal MVP feature list (order to implement; builds value fast)

Aim to get a useful product at each milestone.

MVP (useful quickly):

Local FastAPI + SQLite schema + simple dev UI endpoints.

Playwright scraper that can be fed a list of company/career URLs and returns parsed job entries (title, location, description, apply link). Hook scraper results into DB. 
PromptCloud

Simple Textual TUI: list jobs, filter new-grad, open job link in browser, mark applied (manual confirm).

Chrome extension (TypeScript): show profiles from local server; fill form text fields; clicking “Apply” opens company link and marks pending in DB.

Post-MVP (adds polish & convenience):
5. Resume upload & per-profile versioning (upload PDF to local server; show history in TUI).
6. Extension UX for resume selection — instructive UI to help user complete file upload manually. Optionally implement native messaging helper for file automation (more complex). 
Medium
+1

7. Robust site-specific extractors for major job platforms; scheduler to re-scrape and surface new jobs (diff-ing by job id + url).
8. Packaging scripts: single-click installer (or Docker compose for dev) and a small launcher.

Implementation details / snippets & recommendations

DB schema (simplified):

jobs(id TEXT PRIMARY KEY, title TEXT, company TEXT, location TEXT, description TEXT, apply_url TEXT, scraped_at DATETIME, is_applied BOOLEAN, applied_at DATETIME, profile_id TEXT)
profiles(id TEXT PRIMARY KEY, name TEXT, email TEXT, phone TEXT, resume_versions JSON)


Scraper: use Playwright Python (async) to open company posting, extract canonical apply link and details. For many listings, raw HTTP + BeautifulSoup + heuristics is faster; use Playwright only for JS-driven sites. 
PromptCloud

Extension → local API: have the extension load http://localhost:PORT/api/profiles on popup open. For security, restrict the local server to 127.0.0.1 and use a random high port or a small token if desired.

Packaging & install story (local-only)

During dev, run everything in Docker or venv. For daily use: ship a tiny launcher that starts the FastAPI service (background), exposes the port, and optionally registers a native messaging manifest for the extension. If you want a totally self-contained single binary for the server + TUI, Go wins — but you'd lose Playwright niceties unless you call Playwright via a helper.

Security & privacy notes

Keep everything on localhost. Do not open ports to LAN. If you later want remote sync, add opt-in encryption and explicit remote server with user consent.

Extensions require permission declarations in manifest.json (host permissions for target sites are intrusive). Use minimal host permissions and document that for your extension.

Which path will actually get you a usable product fastest?

If you want absolute fastest development and iteration with good reliability: Python FastAPI + Playwright + Textual + TypeScript extension that talks to localhost. Playwright and Textual let you prototype and iterate rapidly. The biggest friction (file upload automation) is a browser security limitation you’ll need to accept or work around with a native helper. 
PromptCloud
+1

If you want easier deployment / single binary and you’re comfortable building more plumbing: Go + chromedp + bubbletea. Slightly more dev work around scraping reliability and TUI polish, but you’ll get a single compiled binary. 
