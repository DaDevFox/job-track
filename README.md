# Job-Track

A local, privacy-focused job tracking and application management system. Think of it as a self-hosted alternative to Simplify.jobs that keeps your data local.

## Features

- **Job Scraping**: Scrape job listings from company career pages using Playwright (JavaScript rendering) or simple HTTP requests
- **New-Grad Filtering**: Automatically detect and filter for entry-level/new-grad positions
- **TUI Interface**: Terminal-based UI for browsing jobs, applying, and tracking applications
- **Profile Management**: Store multiple profiles with different resumes for different job types
- **Resume Versioning**: Keep track of resume versions and which version was used for each application
- **Chrome Extension**: Autofill job application forms with your profile data
- **Local API**: FastAPI server running on localhost for extension communication

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/DaDevFox/job-track.git
cd job-track

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .

# Install Playwright browsers (for web scraping)
playwright install chromium
```

### Usage

#### Start the TUI
```bash
job-track tui
# or simply:
job-track
```

#### Start the API Server (for Chrome extension)
```bash
job-track api
```

#### Scrape Jobs
```bash
# Scrape from career pages
job-track scrape https://company.com/careers https://another.com/jobs

# Filter for new-grad positions only
job-track scrape --new-grad https://company.com/careers
```

#### Manage Profiles
```bash
# List profiles
job-track profile list

# Add a new profile
job-track profile add --name "John Doe" --email "john@example.com" --phone "+1-555-555-5555"
```

### TUI Keybindings

| Key | Action |
|-----|--------|
| `Enter` | Open job link in browser (marks as pending) |
| `d` | View job details |
| `a` | Mark job as applied (shows confirmation dialog) |
| `p` | Select active profile |
| `n` | Create new profile |
| `f` | Toggle filter presets |
| `/` | Focus search input |
| `r` | Refresh job list |
| `q` | Quit |

## Chrome Extension

The extension allows you to autofill job application forms with your profile data.

### Installation

1. Start the API server: `job-track api`
2. Open Chrome/Edge and go to `chrome://extensions`
3. Enable "Developer mode"
4. Click "Load unpacked" and select the `extension/` directory

### Usage

1. Navigate to a job application page
2. Click the Job-Track extension icon
3. Select your profile
4. Click "Autofill Form"

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   Chrome Ext    │────▶│   FastAPI       │
│   (Autofill)    │     │   localhost     │
└─────────────────┘     └────────┬────────┘
                                 │
                                 ▼
┌─────────────────┐     ┌─────────────────┐
│   Textual TUI   │────▶│   SQLite DB     │
│   (Main UI)     │     │   ~/.local/...  │
└─────────────────┘     └─────────────────┘
                                 ▲
                                 │
┌─────────────────┐              │
│   Playwright    │──────────────┘
│   Scraper       │
└─────────────────┘
```

## Data Storage

All data is stored locally in `~/.local/share/job-track/`:
- `job_track.db` - SQLite database with jobs and profiles
- `resumes/<profile_id>/` - Resume PDF files with versioning

## Testing the Scraper

Use the test script to validate scraping functionality:

```bash
# Test with sample HTML (no network required)
python scripts/test_scrape.py --test

# Test simple HTTP scraping
python scripts/test_scrape.py --simple https://example.com/careers

# Test with Playwright (JavaScript rendering)
python scripts/test_scrape.py https://example.com/careers
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=job_track
```

## License

MIT