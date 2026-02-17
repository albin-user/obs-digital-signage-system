#!/bin/bash
# ============================================================================
# OBS Digital Signage System - Health Check Script
# ============================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "===================================================================="
echo " OBS Digital Signage System - Health Check"
echo "===================================================================="
echo ""

# Check if Python process is running
PYTHON_PID=$(pgrep -f "python.*src/main.py" 2>/dev/null)
if [ -n "$PYTHON_PID" ]; then
    echo -e "${GREEN}[OK]${NC}   Signage system running (PID: $PYTHON_PID)"
else
    echo -e "${RED}[FAIL]${NC} Signage system is NOT running"
fi

# Check if OBS is running
OBS_PID=$(pgrep -x obs 2>/dev/null)
if [ -n "$OBS_PID" ]; then
    echo -e "${GREEN}[OK]${NC}   OBS Studio running (PID: $OBS_PID)"
else
    echo -e "${RED}[FAIL]${NC} OBS Studio is NOT running"
fi

# Check log file age
LOG_FILE="$SCRIPT_DIR/logs/digital_signage.log"
if [ -f "$LOG_FILE" ]; then
    LOG_AGE=$(( $(date +%s) - $(stat -c %Y "$LOG_FILE" 2>/dev/null || stat -f %m "$LOG_FILE" 2>/dev/null) ))
    if [ "$LOG_AGE" -lt 120 ]; then
        echo -e "${GREEN}[OK]${NC}   Last log entry: ${LOG_AGE}s ago"
    else
        echo -e "${YELLOW}[WARN]${NC} Last log entry: ${LOG_AGE}s ago (>2 min)"
    fi
else
    echo -e "${YELLOW}[WARN]${NC} No log file found"
fi

# Count content files (search project dir, excluding venv and logs)
CONTENT_FILES=$(find "$SCRIPT_DIR" -type f \( -name "*.mp4" -o -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.mov" -o -name "*.webm" -o -name "*.mkv" -o -name "*.avi" -o -name "*.bmp" -o -name "*.gif" -o -name "*.webp" \) -not -path "*/venv/*" -not -path "*/logs/*" -not -path "*/.git/*" 2>/dev/null | wc -l)
echo -e "         Media files: $CONTENT_FILES"

# Check disk space
DISK_USAGE=$(df -h "$SCRIPT_DIR" 2>/dev/null | tail -1 | awk '{print $5}')
DISK_AVAIL=$(df -h "$SCRIPT_DIR" 2>/dev/null | tail -1 | awk '{print $4}')
echo -e "         Disk: ${DISK_USAGE} used, ${DISK_AVAIL} available"

# Check recent errors
if [ -f "$SCRIPT_DIR/logs/errors.log" ]; then
    RECENT_ERRORS=$(tail -50 "$SCRIPT_DIR/logs/errors.log" 2>/dev/null | grep -c "$(date +%Y-%m-%d)")
    if [ "$RECENT_ERRORS" -gt 0 ]; then
        echo -e "${YELLOW}[WARN]${NC} $RECENT_ERRORS error(s) in log today"
    else
        echo -e "${GREEN}[OK]${NC}   No errors logged today"
    fi
fi

# Check web UI
WEB_PORT=${WEB_UI_PORT:-80}
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${WEB_PORT}/" 2>/dev/null | grep -q "200"; then
    echo -e "${GREEN}[OK]${NC}   Web UI accessible on port ${WEB_PORT}"
else
    echo -e "${YELLOW}[WARN]${NC} Web UI not responding on port ${WEB_PORT}"
fi

echo ""
echo "===================================================================="
echo ""
