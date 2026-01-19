#!/bin/bash
# Integration test runner script
# Starts chronyd and waits for the socket before running tests

set -e

# Force line-buffered output for CI visibility
exec 1> >(stdbuf -oL cat)
exec 2> >(stdbuf -oL cat >&2)

SOCKET_PATH="/run/chrony/chronyd.sock"
MAX_WAIT=30

echo "=== Integration Test Runner ==="
echo "Checking chronyd installation..."
command -v chronyd >/dev/null 2>&1 || { echo "ERROR: chronyd not found"; exit 1; }
chronyd --version || true

echo "Checking chrony directory permissions..."
ls -la /run/chrony/ || true

echo "Starting chronyd in debug mode..."

# Start chronyd in debug mode to see any errors, then background it
chronyd -d 2>&1 &
CHRONYD_PID=$!
echo "chronyd started with PID: $CHRONYD_PID"

echo "Waiting for chronyd socket at ${SOCKET_PATH}..."

# Wait for the socket to be created
waited=0
while [ ! -S "$SOCKET_PATH" ]; do
    # Check if chronyd is still running
    if ! kill -0 "$CHRONYD_PID" 2>/dev/null; then
        echo "ERROR: chronyd process (PID $CHRONYD_PID) has exited unexpectedly"
        echo "Checking for chronyd processes..."
        ps aux | grep chronyd || true
        echo "Checking socket directory..."
        ls -la /run/chrony/ || true
        exit 1
    fi

    if [ $waited -ge $MAX_WAIT ]; then
        echo "ERROR: Timed out waiting for chronyd socket after ${MAX_WAIT} seconds"
        echo "Checking chronyd process..."
        ps aux | grep chronyd || true
        echo "Checking socket directory..."
        ls -la /run/chrony/ || true
        exit 1
    fi
    sleep 1
    waited=$((waited + 1))
    echo "  Waiting... ($waited seconds)"
done

echo "chronyd socket ready!"
ls -la /run/chrony/

# Make socket and directory accessible to all users (required since usermod group change
# doesn't take effect in current session, and SOCK_DGRAM clients need to create
# their own socket in the directory for bidirectional communication)
chmod 777 /run/chrony
chmod 666 "$SOCKET_PATH"

echo "Socket permissions after chmod:"
ls -la /run/chrony/

echo "Verifying Python version..."
uv run python --version || { echo "ERROR: Python not available via uv"; exit 1; }

echo "Running integration tests..."
exec uv run pytest tests/integration -v "$@"
