#!/bin/bash
# ============================================================================
# OBS Digital Signage - Health Check (pre-flight diagnostics)
# Runs config/OBS/WebDAV/FFprobe checks and prints a plain-language summary.
# ============================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "[ERROR] Virtual environment not found. Run ./install.sh first."
    exit 1
fi

source venv/bin/activate
export ENVIRONMENT=production
python src/main.py --check
EXIT=$?
deactivate 2>/dev/null
exit $EXIT
