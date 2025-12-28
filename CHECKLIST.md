Init repo + choose stack (Python or Go).

Create SQLite schema + minimal FastAPI endpoints (jobs, profiles).

Implement a Playwright script that scrapes one target site and writes to DB. Validate parsing for job title/location/description/apply link. 
PromptCloud

Make a minimal Textual TUI to list DB jobs and mark applied.

Scaffold extension popup that fetches /api/profiles and offers profile selection + fills text fields on document using content script.

Wire “open apply link” flow: extension sets job as pending in DB; TUI shows pending items; when user returns, prompt to confirm applied.

Add resume upload endpoint + UI in TUI and extension (uploads to local server). Implement versioning (timestamped filenames).

(Optional) Add native messaging or local helper for advanced file automation if you need it.
