# Contributing to Job Track

Thank you for your interest in contributing to Job Track!

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/DaDevFox/job-track.git
cd job-track
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run tests:
```bash
pytest tests/ -v
```

## Running the Application

1. Start the API server (in one terminal):
```bash
./start_api.sh
```

2. Start the TUI (in another terminal):
```bash
./start_tui.sh
```

## Testing

We use pytest for testing. Run all tests:
```bash
pytest tests/ -v
```

Run specific test categories:
```bash
pytest tests/test_api.py -v       # API tests
pytest tests/test_models.py -v    # Database tests
pytest tests/test_scraper.py -v   # Scraper tests
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Add docstrings to functions and classes
- Keep functions focused and small

## Adding New Features

### Adding New Job Sources

To add real job scraping capabilities:

1. Edit `backend/scraper.py`
2. Implement scraping logic for your target site
3. Always check robots.txt and terms of service
4. Add appropriate rate limiting and error handling
5. Add tests for your scraper

### Extending the API

1. Add new endpoints in `backend/main.py`
2. Update schemas in `backend/schemas.py` if needed
3. Add tests in `tests/test_api.py`
4. Update README with new endpoints

### Enhancing the TUI

1. Edit `tui/app.py`
2. Add new screens or widgets as needed
3. Update CSS styling in the JobTrackApp class
4. Test manually in a terminal

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for your changes
5. Run the test suite
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Questions?

Feel free to open an issue for any questions or concerns!
