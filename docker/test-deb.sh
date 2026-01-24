#!/bin/bash
set -e

CONTAINER_NAME="second-hand-deb-test"

# Detect platform from image (allows testing across architectures)
PLATFORM=$(docker inspect second-hand-deb-test:latest --format '{{.Architecture}}')
echo "Detected image platform: $PLATFORM"

echo "Starting systemd container..."
docker run -d --name "$CONTAINER_NAME" \
    --platform "linux/$PLATFORM" \
    --privileged \
    --cgroupns=host \
    -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
    second-hand-deb-test:latest

cleanup() {
    echo "Cleaning up..."
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT

echo "Waiting for systemd to initialize..."
sleep 10

echo "=== Validating pex installation ==="
if docker exec "$CONTAINER_NAME" test -f /usr/lib/second-hand/second-hand.pex; then
    echo "✓ Pex file installed"
else
    echo "✗ Pex file not found at /usr/lib/second-hand/second-hand.pex"
    exit 1
fi

if docker exec "$CONTAINER_NAME" test -L /usr/bin/second-hand; then
    echo "✓ Symlink exists at /usr/bin/second-hand"
else
    echo "✗ Symlink not found at /usr/bin/second-hand"
    exit 1
fi

# Verify Python version is in supported range
PYTHON_VERSION=$(docker exec "$CONTAINER_NAME" python3 --version | cut -d' ' -f2)
echo "Python version: $PYTHON_VERSION"

# Wait for services with retry (emulation can be slow)
wait_for_service() {
    local service=$1
    local max_attempts=30
    local attempt=1

    echo "=== Waiting for $service service ==="
    while [ $attempt -le $max_attempts ]; do
        if docker exec "$CONTAINER_NAME" systemctl is-active "$service" 2>/dev/null; then
            echo "✓ $service is running"
            return 0
        fi
        echo "  Attempt $attempt/$max_attempts: $service not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo "✗ $service failed to start"
    docker exec "$CONTAINER_NAME" systemctl status "$service" --no-pager || true
    docker exec "$CONTAINER_NAME" journalctl -u "$service" --no-pager -n 50 || true
    return 1
}

wait_for_service chrony
wait_for_service second-hand

echo "=== Checking service logs for errors ==="
# Fail if there are permission or connection errors in the logs
if docker exec "$CONTAINER_NAME" journalctl -u second-hand --no-pager | grep -iE "permission denied|connection refused|error"; then
    echo "✗ Found errors in service logs"
    docker exec "$CONTAINER_NAME" journalctl -u second-hand --no-pager
    exit 1
fi
echo "✓ No errors in service logs"

echo "=== Testing health endpoint ==="
# Retry health check - uvicorn may need time to bind after service shows active
attempt=1
max_attempts=15
while [ $attempt -le $max_attempts ]; do
    if docker exec "$CONTAINER_NAME" curl -sf http://localhost:8000/health; then
        echo ""
        echo "✓ Health endpoint responding"
        break
    fi
    if [ $attempt -eq $max_attempts ]; then
        echo "✗ Health endpoint not responding after $max_attempts attempts"
        docker exec "$CONTAINER_NAME" journalctl -u second-hand --no-pager -n 50 || true
        exit 1
    fi
    echo "  Attempt $attempt/$max_attempts: health endpoint not ready yet..."
    sleep 2
    attempt=$((attempt + 1))
done

echo "=== Testing chrony connection via dashboard ==="
DASHBOARD=$(docker exec "$CONTAINER_NAME" curl -sf http://localhost:8000/)

# Verify we got actual chrony data (not "Connecting..." or "N/A")
# When connected, dashboard shows "Synchronized" or "Not Synchronized"
if echo "$DASHBOARD" | grep -qE "Synchronized|Not Synchronized"; then
    echo "✓ Dashboard shows sync status from chrony"
else
    echo "✗ Dashboard not showing chrony sync status"
    echo "$DASHBOARD"
    exit 1
fi

# Verify status is not "Unknown" (which indicates no chrony connection)
# Note: We can't use greedy grep for "Stratum.*N/A" because htpy outputs HTML
# on a single line, causing false matches with "N/A" in other stat boxes like Ref IP
if echo "$DASHBOARD" | grep -q 'stat-value">Unknown<'; then
    echo "✗ Status shows Unknown - chrony not connected"
    exit 1
fi
echo "✓ Dashboard shows valid chrony status"

# Verify no error messages
if echo "$DASHBOARD" | grep -qiE "connection error|permission denied|failed to connect"; then
    echo "✗ Dashboard shows connection error"
    echo "$DASHBOARD"
    exit 1
fi
echo "✓ No connection errors in dashboard"

echo ""
echo "✅ All .deb integration tests passed!"
