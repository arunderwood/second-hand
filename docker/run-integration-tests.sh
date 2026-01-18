#!/bin/bash
# Integration test runner script
# Starts chronyd and waits for the socket before running tests

set -e

SOCKET_PATH="/run/chrony/chronyd.sock"
MAX_WAIT=30

echo "Starting chronyd..."

# Start chronyd in debug mode to see any errors, then background it
chronyd -d &
CHRONYD_PID=$!

echo "Waiting for chronyd socket at ${SOCKET_PATH}..."

# Wait for the socket to be created
waited=0
while [ ! -S "$SOCKET_PATH" ]; do
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

# Make socket and directory accessible to all users (required since usermod group change
# doesn't take effect in current session, and SOCK_DGRAM clients need to create
# their own socket in the directory for bidirectional communication)
chmod 777 /run/chrony
chmod 666 "$SOCKET_PATH"

echo "Running integration tests..."
exec uv run pytest tests/integration -v "$@"
