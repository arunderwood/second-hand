#!/bin/bash
set -e

CONTAINER_NAME="second-hand-deb-test"

# Ceiling for `systemd-analyze security`. --threshold takes the internal 0-100
# scale, which is ten times the exposure level the tool prints: 20 here is the
# "2.0" a reader sees. The hardened unit scores 1.5 on systemd 252-257, so this
# leaves room for new checks in later systemd releases while still catching a
# directive being dropped.
SECURITY_THRESHOLD="${SECURITY_THRESHOLD:-20}"

# Separate ceiling for second-hand-reader.service: it runs as a static user
# (_chrony — inheriting chronyd's socket access is its whole point), which
# scores worse than DynamicUser, so its ceiling sits higher than the web
# unit's while still pinning the hardening block.
READER_SECURITY_THRESHOLD="${READER_SECURITY_THRESHOLD:-45}"

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

# Each request opens a fresh chronyd connection, so the dashboard reflects a
# chrony restart as soon as the new daemon binds its socket.
wait_for_dashboard() {
    local pattern=$1
    local max_attempts=15
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if docker exec "$CONTAINER_NAME" curl -s http://localhost:8000/ | grep -qE "$pattern"; then
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    return 1
}

wait_for_service chrony
wait_for_service second-hand

# UPGRADE_TO names a newer .deb. The image then holds an older release, and the
# upgrade happens here with systemd running, as it would on a real host: the
# maintainer scripts of both versions run and the service is restarted. Every
# check below then runs against the upgraded package.
if [ -n "${UPGRADE_TO:-}" ]; then
    echo "=== Upgrading to $(basename "$UPGRADE_TO") ==="
    health() { docker exec "$CONTAINER_NAME" curl -sf http://localhost:8000/health; }
    attempt=1
    until OLD_HEALTH=$(health); do
        [ $attempt -ge 15 ] && { echo "✗ Old version never became healthy"; exit 1; }
        sleep 2; attempt=$((attempt + 1))
    done
    echo "Before: $OLD_HEALTH"

    docker cp "$UPGRADE_TO" "$CONTAINER_NAME":/tmp/upgrade.deb
    # The image dropped its package lists; without them apt cannot fetch a
    # Recommends the new version adds, which a real host would install.
    docker exec "$CONTAINER_NAME" apt-get update -qq
    if ! docker exec "$CONTAINER_NAME" apt-get install -y /tmp/upgrade.deb; then
        echo "✗ apt-get could not upgrade the package"
        exit 1
    fi
    wait_for_service second-hand

    attempt=1
    until NEW_HEALTH=$(health) && [ "$NEW_HEALTH" != "$OLD_HEALTH" ]; do
        [ $attempt -ge 15 ] && { echo "✗ Service still reports ${NEW_HEALTH:-nothing} after upgrade"; exit 1; }
        sleep 2; attempt=$((attempt + 1))
    done
    echo "After: $NEW_HEALTH"
    echo "✓ Upgraded in place and restarted"
fi

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

# The font allowlist hard-codes paths inside the distro font packages. A renamed
# file in a new release would quietly drop the dashboard to system fonts.
# fonts-ibm-plex is only checked where the image could install it: Debian keeps
# it in contrib, which the test images do not enable.
echo "=== Testing fonts from the distro font packages ==="
FONTS=(jetbrains-mono-{400,500,600,700})
if docker exec "$CONTAINER_NAME" dpkg -s fonts-ibm-plex > /dev/null 2>&1; then
    FONTS+=(ibm-plex-sans-{400,500,600})
else
    echo "  fonts-ibm-plex not installed here; skipping IBM Plex Sans"
fi
for font in "${FONTS[@]}"; do
    if docker exec "$CONTAINER_NAME" curl -sf -o /dev/null "http://localhost:8000/fonts/${font}.ttf"; then
        echo "✓ /fonts/${font}.ttf served"
    else
        echo "✗ /fonts/${font}.ttf not served; check the paths in second_hand/fonts.py"
        exit 1
    fi
done

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

# The dashboard reads chronyd's command port, so "cmdport 0" is the realistic way
# an operator breaks it. The failure must stay a rendered message: pychrony raises
# ChronyConnectionError here, which the service catches, and a regression to an
# uncaught error would surface as a 500 rather than anything the positive tests see.
echo "=== Testing graceful degradation when chronyd's command port is disabled ==="
docker exec "$CONTAINER_NAME" sh -c 'echo "cmdport 0" >> /etc/chrony/chrony.conf'
docker exec "$CONTAINER_NAME" systemctl restart chrony
if ! wait_for_dashboard "Unable to connect to chronyd"; then
    echo "✗ Dashboard never showed the chronyd connection message"
    docker exec "$CONTAINER_NAME" curl -s http://localhost:8000/ || true
    docker exec "$CONTAINER_NAME" journalctl -u second-hand --no-pager -n 30 || true
    exit 1
fi

BROKEN_CODE=$(docker exec "$CONTAINER_NAME" curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)
if [ "$BROKEN_CODE" != "200" ]; then
    echo "✗ Dashboard returned HTTP $BROKEN_CODE with the command port disabled, expected 200"
    docker exec "$CONTAINER_NAME" journalctl -u second-hand --no-pager -n 30 || true
    exit 1
fi
echo "✓ Dashboard still returns 200 with the command port disabled"

BROKEN=$(docker exec "$CONTAINER_NAME" curl -s http://localhost:8000/)
if echo "$BROKEN" | grep -qi "Unable to connect to chronyd"; then
    echo "✓ Dashboard explains the failure instead of erroring out"
else
    echo "✗ Dashboard did not show the chronyd connection message"
    echo "$BROKEN"
    exit 1
fi

if docker exec "$CONTAINER_NAME" journalctl -u second-hand --no-pager | grep -qE "Traceback|ChronyDataError"; then
    echo "✗ Unhandled exception while the command port was disabled"
    docker exec "$CONTAINER_NAME" journalctl -u second-hand --no-pager -n 40
    exit 1
fi
echo "✓ No unhandled exceptions"

docker exec "$CONTAINER_NAME" sh -c 'sed -i "/^cmdport 0$/d" /etc/chrony/chrony.conf'
docker exec "$CONTAINER_NAME" systemctl restart chrony
if wait_for_dashboard "Synchronized|Not Synchronized"; then
    echo "✓ Dashboard recovers once the command port is restored"
else
    echo "✗ Dashboard did not recover after restoring the command port"
    exit 1
fi

echo "=== Checking systemd hardening score ==="
# systemd-analyze security needs the unit loaded, which is why this runs against
# the live container rather than as a static lint on debian/second-hand.service.
if docker exec "$CONTAINER_NAME" \
    systemd-analyze security --threshold="$SECURITY_THRESHOLD" --no-pager second-hand.service; then
    echo "✓ Hardening score within the ${SECURITY_THRESHOLD} ceiling"
else
    echo "✗ second-hand.service exposure exceeds the ${SECURITY_THRESHOLD} ceiling"
    echo "  Restore the dropped hardening directive, or raise SECURITY_THRESHOLD"
    echo "  in this script if the increase is a deliberate, understood tradeoff."
    exit 1
fi

# =============================================================================
# Client visibility: reader service, snapshot channel, panel, off routes
# =============================================================================

# Polls /api/clients until its body matches a pattern. The reader publishes on
# its own cycle and the web side caches the unit state for 5 s, so every state
# change needs a wait, not an instant assert.
wait_for_clients_api() {
    local pattern=$1
    local max_attempts=${2:-30}
    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        if docker exec "$CONTAINER_NAME" curl -s http://localhost:8000/api/clients | grep -qE "$pattern"; then
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    echo "✗ /api/clients never matched: $pattern"
    docker exec "$CONTAINER_NAME" curl -s http://localhost:8000/api/clients || true
    docker exec "$CONTAINER_NAME" journalctl -u second-hand-reader --no-pager -n 20 || true
    clients_diagnostics
    return 1
}

# What the reader's chronyc actually sees, for failures that only reproduce
# on some CI runners: chronyc's unix client socket lives in subdirectories it
# creates under /run/chrony, so sandbox mount state and the host's sysctls
# both matter.
clients_diagnostics() {
    echo "--- diagnostics: environment"
    uname -a
    docker exec "$CONTAINER_NAME" sh -c 'sysctl fs.protected_regular fs.protected_fifos fs.protected_symlinks fs.protected_hardlinks 2>/dev/null' || true
    echo "--- diagnostics: /run/chrony and chrony journal"
    docker exec "$CONTAINER_NAME" ls -la /run/chrony/ || true
    docker exec "$CONTAINER_NAME" journalctl -u chrony --no-pager -n 20 || true
    echo "--- diagnostics: bare chronyc as _chrony (no sandbox)"
    # The whole script runs under set -e, and most of these probes are
    # expected to fail here: every line must be guarded or the dump cuts off
    # at the first finding.
    docker exec "$CONTAINER_NAME" runuser -u _chrony -- chronyc -c -n clients -k || echo "rc=$?"
    echo "--- diagnostics: bind and connect split (exact errno)"
    docker exec "$CONTAINER_NAME" runuser -u _chrony -- python3 -c '
import os, socket
os.makedirs("/run/chrony/diagprobe/x", mode=0o711, exist_ok=True)
s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
try:
    s.bind("/run/chrony/diagprobe/x/sock")
    print("bind: ok")
except OSError as e:
    print("bind:", e)
try:
    s.connect("/run/chrony/chronyd.sock")
    print("connect: ok")
except OSError as e:
    print("connect:", e)
' || true
    docker exec "$CONTAINER_NAME" sh -c 'rm -rf /run/chrony/diagprobe' || true
    echo "--- diagnostics: confinement and denials"
    docker exec "$CONTAINER_NAME" cat /proc/1/attr/current 2>/dev/null || true
    sudo dmesg 2>/dev/null | grep -iE 'apparmor|DENIED' | tail -15 || true
    echo "--- diagnostics: chronyc syscall trace"
    docker exec "$CONTAINER_NAME" sh -c 'apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq strace >/dev/null 2>&1; runuser -u _chrony -- strace -f -e trace=socket,bind,connect,mkdir chronyc -c -n clients -k 2>&1 | tail -15' || true
    echo "--- diagnostics: chronyc inside a replica of the reader sandbox"
    docker exec "$CONTAINER_NAME" systemd-run --unit=clients-diag --wait --pipe --quiet \
        -p User=_chrony -p Group=second-hand-data \
        -p NoNewPrivileges=yes -p ProtectSystem=strict -p ProtectHome=yes \
        -p PrivateTmp=yes -p PrivateDevices=yes -p ProtectClock=yes \
        -p ProtectHostname=yes -p ProtectKernelLogs=yes -p ProtectKernelModules=yes \
        -p ProtectKernelTunables=yes -p ProtectControlGroups=yes \
        -p ProtectProc=invisible -p ProcSubset=pid -p RestrictNamespaces=yes \
        -p RestrictRealtime=yes -p RestrictSUIDSGID=yes -p LockPersonality=yes \
        -p RemoveIPC=yes -p UMask=0027 -p SystemCallArchitectures=native \
        -p SystemCallFilter=@system-service -p SystemCallErrorNumber=EPERM \
        -p CapabilityBoundingSet= -p RestrictAddressFamilies=AF_UNIX \
        -p IPAddressDeny=any -p RuntimeDirectory=clients-diag \
        sh -c 'ls -ld /run/chrony; touch /run/chrony/diagprobe 2>&1 && rm -f /run/chrony/diagprobe; chronyc -c -n clients -k; echo "sandboxed chronyc rc=$?"' || true
    echo "--- diagnostics: effective reader unit properties"
    docker exec "$CONTAINER_NAME" systemctl show second-hand-reader -p User,ProtectSystem,RestrictAddressFamilies,RuntimeDirectory,NoNewPrivileges --no-pager || true
}

clients_api_status() {
    docker exec "$CONTAINER_NAME" curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/clients
}

echo "=== Clients: reader service starts with the package ==="
wait_for_service second-hand-reader

# A 10 s cycle keeps the state-change waits below the default 30 s interval;
# it also proves the conffile reaches the reader.
docker exec "$CONTAINER_NAME" sh -c 'echo "SECOND_HAND_READER_INTERVAL=10" >> /etc/default/second-hand'
docker exec "$CONTAINER_NAME" systemctl restart second-hand-reader

echo "=== Clients: snapshot permissions (R2) ==="
attempt=1
until docker exec "$CONTAINER_NAME" test -f /run/second-hand-reader/snapshot.json; do
    [ $attempt -ge 20 ] && { echo "✗ Reader never published a snapshot"; docker exec "$CONTAINER_NAME" journalctl -u second-hand-reader --no-pager -n 30; exit 1; }
    sleep 2; attempt=$((attempt + 1))
done
SNAP_STAT=$(docker exec "$CONTAINER_NAME" stat -c '%a %U %G' /run/second-hand-reader/snapshot.json)
if [ "$SNAP_STAT" = "640 _chrony second-hand-data" ]; then
    echo "✓ Snapshot file is 0640 _chrony:second-hand-data"
else
    echo "✗ Snapshot file is '$SNAP_STAT', expected '640 _chrony second-hand-data'"
    exit 1
fi
DIR_STAT=$(docker exec "$CONTAINER_NAME" stat -c '%a %U %G' /run/second-hand-reader)
if [ "$DIR_STAT" = "750 _chrony second-hand-data" ]; then
    echo "✓ Snapshot directory is 0750 _chrony:second-hand-data"
else
    echo "✗ Snapshot directory is '$DIR_STAT', expected '750 _chrony second-hand-data'"
    exit 1
fi
if docker exec "$CONTAINER_NAME" runuser -u nobody -- cat /run/second-hand-reader/snapshot.json >/dev/null 2>&1; then
    echo "✗ Unrelated users can read the snapshot (client addresses leak locally)"
    exit 1
fi
echo "✓ Unrelated users cannot read the snapshot"

echo "=== Clients: panel shows real traffic out of the box (SC-001) ==="
# Mode-3 NTP requests from 127.0.0.1; chronyd's client log records them.
docker exec "$CONTAINER_NAME" python3 -c '
import socket, time
for _ in range(5):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(5)
    s.sendto(bytes([0x23]) + bytes(47), ("127.0.0.1", 123))
    s.recvfrom(1024)
    s.close()
    time.sleep(0.2)
'
# The reader only sees the traffic on its next cycle, so wait for a non-zero
# count rather than asserting the instant the first (possibly pre-traffic)
# snapshot appears.
wait_for_clients_api '"total_clients":[1-9]'
echo "✓ /api/clients reports clients after synthetic traffic"
if docker exec "$CONTAINER_NAME" curl -s http://localhost:8000/ | grep -q "NTP Clients"; then
    echo "✓ Dashboard page renders the Clients panel"
else
    echo "✗ Clients panel missing from the dashboard page"
    exit 1
fi

echo "=== Clients: reader hardening ceiling ==="
if docker exec "$CONTAINER_NAME" \
    systemd-analyze security --threshold="$READER_SECURITY_THRESHOLD" --no-pager second-hand-reader.service; then
    echo "✓ Reader score within the ${READER_SECURITY_THRESHOLD} ceiling"
else
    echo "✗ second-hand-reader.service exposure exceeds the ${READER_SECURITY_THRESHOLD} ceiling"
    exit 1
fi

echo "=== Clients: memory ceilings (SC-004) ==="
# Anonymous memory, not MemoryCurrent: the cgroup's memory.current counts the
# page cache of the extracted pex (~50 MB of reclaimable file pages), which
# says nothing about what the process actually holds.
check_memory() {
    local unit=$1 limit_mb=$2
    local cgroup bytes
    cgroup=$(docker exec "$CONTAINER_NAME" systemctl show -p ControlGroup --value "$unit")
    bytes=$(docker exec "$CONTAINER_NAME" awk '/^anon /{print $2}' "/sys/fs/cgroup${cgroup}/memory.stat" 2>/dev/null)
    if [ -z "$bytes" ]; then
        echo "  $unit: anonymous memory not readable, skipping"
        return 0
    fi
    if [ "$bytes" -lt $((limit_mb * 1024 * 1024)) ]; then
        echo "✓ $unit uses $((bytes / 1024 / 1024)) MB anonymous (< ${limit_mb} MB)"
    else
        echo "✗ $unit uses $((bytes / 1024 / 1024)) MB anonymous (ceiling ${limit_mb} MB)"
        return 1
    fi
}
check_memory second-hand.service 100
check_memory second-hand-reader.service 64

echo "=== Clients: degradation states (FR-017) ==="
docker exec "$CONTAINER_NAME" systemctl stop chrony
wait_for_clients_api '"reason":"chronyd_unreachable"'
echo "✓ Stopped chronyd reads as chronyd_unreachable"
CODE=$(docker exec "$CONTAINER_NAME" curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)
[ "$CODE" = "200" ] || { echo "✗ Dashboard returned $CODE while chronyd was down"; exit 1; }
echo "✓ Dashboard stays 200"

docker exec "$CONTAINER_NAME" sh -c 'echo "noclientlog" >> /etc/chrony/chrony.conf'
docker exec "$CONTAINER_NAME" systemctl start chrony
wait_for_clients_api '"reason":"client_logging_disabled"'
echo "✓ noclientlog reads as client_logging_disabled"
docker exec "$CONTAINER_NAME" sh -c 'sed -i "/^noclientlog$/d" /etc/chrony/chrony.conf'
docker exec "$CONTAINER_NAME" systemctl restart chrony
wait_for_clients_api '"status":"ok"'

echo "=== Clients: stopped reader is unavailable, not absent (R3) ==="
# RuntimeDirectory= removes the snapshot on stop; classifying what remains
# requires the hardened web unit to run `systemctl show` successfully, which
# is exactly the R3 assumption this verifies.
docker exec "$CONTAINER_NAME" systemctl stop second-hand-reader
wait_for_clients_api '"reason":"reader_not_running"'
echo "✓ Enabled-but-stopped reader reads as reader_not_running"
docker exec "$CONTAINER_NAME" systemctl start second-hand-reader
wait_for_clients_api '"status":"ok"'

echo "=== Clients: off route a — configuration flag (FR-016) ==="
docker exec "$CONTAINER_NAME" sh -c 'echo "SECOND_HAND_CLIENTS_ENABLED=false" >> /etc/default/second-hand'
docker exec "$CONTAINER_NAME" systemctl restart second-hand second-hand-reader || true
attempt=1
until [ "$(clients_api_status)" = "404" ]; do
    [ $attempt -ge 15 ] && { echo "✗ /api/clients still answers with the flag off"; exit 1; }
    sleep 2; attempt=$((attempt + 1))
done
echo "✓ /api/clients is 404"
if docker exec "$CONTAINER_NAME" curl -s http://localhost:8000/ | grep -q "NTP Clients"; then
    echo "✗ Clients panel still on the page with the flag off"
    exit 1
fi
echo "✓ Panel absent from the page"
READER_STATE=$(docker exec "$CONTAINER_NAME" systemctl is-active second-hand-reader || true)
if [ "$READER_STATE" = "active" ] || [ "$READER_STATE" = "failed" ]; then
    echo "✗ Reader is '$READER_STATE' with the flag off; it must exit 0 and stay down"
    exit 1
fi
echo "✓ Reader exited cleanly and is $READER_STATE"

docker exec "$CONTAINER_NAME" sh -c 'sed -i "/^SECOND_HAND_CLIENTS_ENABLED=false$/d" /etc/default/second-hand'
docker exec "$CONTAINER_NAME" systemctl restart second-hand second-hand-reader
wait_for_clients_api '"status":"ok"'
echo "✓ Panel returns once the flag is removed"

echo "=== Clients: off route b — disabled unit (FR-016) ==="
docker exec "$CONTAINER_NAME" systemctl disable --now second-hand-reader
attempt=1
until [ "$(clients_api_status)" = "404" ]; do
    [ $attempt -ge 15 ] && { echo "✗ /api/clients still answers with the reader disabled"; exit 1; }
    sleep 2; attempt=$((attempt + 1))
done
echo "✓ /api/clients is 404 with the unit disabled"
if docker exec "$CONTAINER_NAME" curl -s http://localhost:8000/ | grep -q "NTP Clients"; then
    echo "✗ Clients panel still on the page with the reader disabled"
    exit 1
fi
echo "✓ Panel absent from the page"

echo "=== Clients: off state survives a package reinstall (SC-006) ==="
# A reinstall runs the same maintainer scripts an upgrade does, so a disabled
# unit staying disabled here is the upgrade-persistence guarantee
# (dh_installsystemd enables units on first install only).
REINSTALL_DEB=$(docker exec "$CONTAINER_NAME" sh -c 'ls /tmp/upgrade.deb 2>/dev/null || ls /tmp/second-hand_*.deb | head -1')
docker exec "$CONTAINER_NAME" apt-get install --reinstall -y "$REINSTALL_DEB" >/dev/null
wait_for_service second-hand
ENABLED_STATE=$(docker exec "$CONTAINER_NAME" systemctl is-enabled second-hand-reader || true)
if [ "$ENABLED_STATE" != "disabled" ]; then
    echo "✗ Reader is '$ENABLED_STATE' after reinstall, expected disabled"
    exit 1
fi
attempt=1
until [ "$(clients_api_status)" = "404" ]; do
    [ $attempt -ge 15 ] && { echo "✗ /api/clients answers after reinstall with the reader disabled"; exit 1; }
    sleep 2; attempt=$((attempt + 1))
done
echo "✓ Reader stays disabled and client data stays off through reinstall"

docker exec "$CONTAINER_NAME" systemctl enable --now second-hand-reader
wait_for_clients_api '"status":"ok"'
echo "✓ Re-enabling the unit brings the panel back without further setup"

echo ""
echo "✅ All .deb integration tests passed!"
