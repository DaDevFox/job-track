# Job Track

A job tracking application with web scraping, application management, and a terminal user interface (TUI). Keep your job search organized with local data storage.

## Features

- 🔍 **Web-scraped Job Listings**: Automatically discover job postings (demo mode included)
- 📝 **Application Tracking**: Track your job applications with status updates
- 💻 **Terminal UI**: Beautiful, interactive TUI for managing jobs and applications
- 🚀 **FastAPI Backend**: RESTful API for all operations
- 💾 **Local Data Storage**: All data stored locally in SQLite database
- ✅ **Fully Tested**: Comprehensive test suite included

## Architecture

- **Backend**: Python FastAPI with SQLAlchemy ORM
- **Database**: SQLite (local storage)
- **TUI**: Textual framework with Rich styling
- **Scraper**: BeautifulSoup4 (demo mode with extensible design)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/DaDevFox/job-track.git
cd job-track
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

Or install as a package:
```bash
pip install -e .
```

## Quick Start

1. **Start the API server** (required for TUI):
```bash
./start_api.sh
```

2. **In a new terminal, start the TUI**:
```bash
./start_tui.sh
```

3. **Or run the example script** to see API usage:
```bash
python example_usage.py
```

## Usage

### Starting the API Server

The backend API must be running for the TUI to work:

```bash
./start_api.sh
# Or manually:
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for interactive API documentation.

### Starting the TUI

In a new terminal window:

```bash
./start_tui.sh
# Or manually:
python -m tui.app
```

### TUI Controls

**Job List Screen:**
- `r` - Refresh job listings
- `s` - Scrape new jobs (demo mode)
- `a` - View applications
- `q` - Quit

**Applications Screen:**
- `r` - Refresh applications
- `n` - Create new application
- `q` - Back to jobs

**Navigation:**
- Arrow keys - Navigate tables
- Tab - Switch between widgets
- Enter - Select/activate

## API Endpoints

### Jobs
- `GET /jobs` - List all jobs
- `GET /jobs/{id}` - Get specific job
- `POST /jobs` - Create new job
- `DELETE /jobs/{id}` - Delete job
- `POST /scrape` - Scrape jobs (with query params: search_term, location)

### Applications
- `GET /applications` - List all applications
- `GET /applications/{id}` - Get specific application
- `POST /applications` - Create new application
- `PATCH /applications/{id}` - Update application
- `DELETE /applications/{id}` - Delete application

## Testing

Run all tests:
```bash
pytest tests/ -v
```

Run specific test files:
```bash
pytest tests/test_api.py -v
pytest tests/test_models.py -v
pytest tests/test_scraper.py -v
```

## Project Structure

```
job-track/
├── backend/
│   ├── __init__.py
│   ├── main.py          # FastAPI application
│   ├── models.py        # SQLAlchemy models
│   ├── schemas.py       # Pydantic schemas
│   └── scraper.py       # Job scraping logic
├── tui/
│   ├── __init__.py
│   └── app.py           # Textual TUI application
├── tests/
│   ├── __init__.py
│   ├── test_api.py      # API endpoint tests
│   ├── test_models.py   # Database model tests
│   └── test_scraper.py  # Scraper tests
├── requirements.txt
├── start_api.sh         # Start API server
├── start_tui.sh         # Start TUI
└── README.md
```

## Development

### Adding New Job Sources

The scraper is designed to be extensible. To add real job scraping:

1. Edit `backend/scraper.py`
2. Implement scraping logic for your target sites
3. Always check robots.txt and terms of service
4. Add appropriate rate limiting and error handling

### Database

The SQLite database (`jobtrack.db`) is created automatically on first run. To reset:

```bash
rm jobtrack.db
```

### Customization

- Modify `backend/models.py` to add new fields
- Update `backend/schemas.py` for API validation
- Customize TUI appearance in `tui/app.py` CSS section

## Future Enhancements

- 🤖 AI/LLM-based skill matching
- 📊 Analytics and statistics dashboard
- 📧 Email notifications for application deadlines
- 🔄 Automated status updates
- 🌐 Multiple job board integrations
- 📱 Web UI in addition to TUI

## License

MIT

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.