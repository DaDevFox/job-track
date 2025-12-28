#!/bin/bash
# Start the TUI application

echo "Starting Job Track TUI..."
cd "$(dirname "$0")"
python -m tui.app
