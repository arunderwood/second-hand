/**
 * Dashboard JavaScript Module
 *
 * Provides real-time countdown animations and auto-refresh functionality
 * for the second-hand NTP dashboard.
 *
 * Features:
 * - Poll countdown timers updating every second
 * - "Time since last receive" display updating every second
 * - Auto-refresh of data at the server's SECOND_HAND_REFRESH_INTERVAL
 * - Hovering a source highlights its row in every table
 * - Progressive enhancement (works without JS)
 *
 * Display strings and row classes come from /api/sources already computed,
 * so the server's formatting rules are the only ones.
 */

const DEFAULT_REFRESH_INTERVAL_S = 30;
const UPDATE_INTERVAL_MS = 1000; // 1 second

// Every class the API's row_class can carry, so the previous one is cleared.
const SOURCE_STATE_CLASSES = [
    'source-selected',
    'source-falseticker',
    'source-jittery',
    'source-unreachable',
];

// State
let refreshIntervalId = null;
let updateIntervalId = null;
let lastRefreshFailed = false;

/**
 * Initialize the dashboard with real-time updates.
 * Called on DOMContentLoaded.
 */
function initDashboard() {
    // Start the 1-second update interval for countdowns and time-since
    updateIntervalId = setInterval(updateTimers, UPDATE_INTERVAL_MS);

    refreshIntervalId = setInterval(refreshData, refreshIntervalSeconds() * 1000);

    initLinkedRowHighlight();

    // Run initial update
    updateTimers();

    console.log('Dashboard initialized with real-time updates');
}

/**
 * Highlight every row for a source while any one of them is hovered.
 *
 * Refreshes patch rows in place, so these listeners last as long as the page.
 */
function initLinkedRowHighlight() {
    const rows = [...document.querySelectorAll('tr[data-address]')];
    const setLinked = (address, linked) => {
        rows.filter(row => row.dataset.address === address)
            .forEach(row => row.classList.toggle('row-linked', linked));
    };

    rows.forEach(row => {
        row.addEventListener('mouseenter', () => setLinked(row.dataset.address, true));
        row.addEventListener('mouseleave', () => setLinked(row.dataset.address, false));
    });
}

/**
 * Read the refresh interval the server rendered onto the page.
 *
 * @returns {number} Seconds between data refreshes
 */
function refreshIntervalSeconds() {
    const dashboard = document.querySelector('.dashboard');
    const seconds = parseInt(dashboard?.dataset.refreshInterval, 10);
    return seconds > 0 ? seconds : DEFAULT_REFRESH_INTERVAL_S;
}

/**
 * Update all countdown timers and time-since displays.
 * Called every second.
 */
function updateTimers() {
    updateCountdowns();
    updateTimeSince();
    updateClientsAge();
}

/**
 * Update all poll countdown displays.
 * Calculates time remaining until next poll based on data attributes.
 */
function updateCountdowns() {
    const now = Math.floor(Date.now() / 1000);
    const countdowns = document.querySelectorAll('.poll[data-poll-interval]');

    countdowns.forEach(cell => {
        const interval = parseFloat(cell.dataset.pollInterval);
        const lastRx = parseInt(cell.dataset.lastRxTime, 10);

        if (isNaN(interval) || isNaN(lastRx)) return;
        // Sub-second polls cycle faster than this one-second tick, so the
        // server-rendered interval stays as the label.
        if (interval < 1) return;

        // Calculate time since last receive
        const elapsed = now - lastRx;

        // Calculate time remaining in current poll cycle
        const remaining = interval - (elapsed % interval);

        // Update the countdown display
        const countdownSpan = cell.querySelector('.countdown');
        if (countdownSpan) {
            countdownSpan.textContent = formatDuration(remaining);
        }
    });
}

/**
 * Update all "time since" displays.
 * Shows time elapsed since last packet received.
 */
function updateTimeSince() {
    const now = Math.floor(Date.now() / 1000);
    const timeSinceElements = document.querySelectorAll('.last-rx[data-timestamp]');

    timeSinceElements.forEach(cell => {
        const timestamp = parseInt(cell.dataset.timestamp, 10);

        if (isNaN(timestamp)) return;

        const elapsed = now - timestamp;

        // Update the time-since display
        const timeSinceSpan = cell.querySelector('.time-since');
        if (timeSinceSpan) {
            timeSinceSpan.textContent = formatDuration(elapsed) + ' ago';
        }
    });
}

/**
 * Format a duration in seconds to human-readable string.
 *
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration (e.g., "45s", "2m 30s", "1h 5m")
 */
function formatDuration(seconds) {
    if (seconds < 0) seconds = 0;

    if (seconds < 60) {
        return `${seconds}s`;
    } else if (seconds < 3600) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}m ${secs}s`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${mins}m`;
    }
}

/**
 * Refresh data from the server API.
 * Called every refresh interval.
 */
async function refreshData() {
    try {
        const response = await fetch('/api/sources');

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        updateDashboard(data);

        // Clear any stale data warning
        if (lastRefreshFailed) {
            lastRefreshFailed = false;
            hideStaleWarning();
        }

    } catch (error) {
        console.error('Failed to refresh data:', error);
        lastRefreshFailed = true;
        showStaleWarning();
    }

    // Independent of sources: a clients failure must not mark source data
    // stale, and vice versa.
    try {
        await refreshClients();
    } catch (error) {
        console.error('Failed to refresh client data:', error);
    }
}

/**
 * Tick the "updated Ns ago" line on the Clients panel.
 * Called every second.
 */
function updateClientsAge() {
    const age = document.querySelector('.clients-age[data-taken-at]');
    if (!age) return;
    const takenAt = parseInt(age.dataset.takenAt, 10);
    if (isNaN(takenAt)) return;
    const elapsed = Math.max(0, Math.floor(Date.now() / 1000) - takenAt);
    age.textContent = `updated ${formatDuration(elapsed)} ago`;
}

/**
 * Refresh the Clients panel from /api/clients.
 *
 * The panel is server-rendered; this updates values in place. Structural
 * changes (feature toggled, availability state changed, table setting
 * flipped) reload the page so the server renders the new shape — the same
 * approach the sources table takes when the source set changes.
 */
async function refreshClients() {
    const panel = document.querySelector('.clients-section');
    const response = await fetch('/api/clients');

    if (response.status === 404) {
        // Feature turned off (or chronyd now remote) since this page was
        // rendered. After the reload the panel is absent and this function
        // returns early, so no reload loop is possible.
        if (panel) window.location.reload();
        return;
    }
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    if (!panel) {
        // Feature turned on since render: fetch a page that includes it.
        window.location.reload();
        return;
    }

    const data = await response.json();
    if (data.status !== panel.dataset.status) {
        window.location.reload();
        return;
    }
    if (data.status === 'unavailable') {
        return; // The server-rendered reason line still applies.
    }
    const tableWrap = panel.querySelector('.clients-table-wrap');
    if (Boolean(tableWrap) !== Boolean(data.table_enabled)) {
        window.location.reload();
        return;
    }

    updateClientsPanel(panel, data);
}

/**
 * Write fresh client values into the panel.
 *
 * @param {Element} panel - The .clients-section element
 * @param {Object} data - /api/clients response with status "ok"
 */
function updateClientsPanel(panel, data) {
    const age = panel.querySelector('.clients-age');
    if (age && data.taken_at) {
        age.dataset.takenAt = data.taken_at;
    }
    const staleBadge = panel.querySelector('.clients-stale-badge');
    if (staleBadge) staleBadge.hidden = !data.stale;

    const summary = data.summary;
    setClientsField(panel, 'total_clients', summary.total_clients);
    setClientsField(panel, 'nts_split', `${summary.nts_clients} / ${summary.ntp_clients}`);
    setClientsField(panel, 'rate_limited_clients', summary.rate_limited_clients);
    setClientsField(panel, 'total_dropped_requests', summary.total_dropped_requests);

    updateBuckets(panel, 'last_seen', summary.last_seen_buckets);
    updateBuckets(panel, 'poll_interval', summary.poll_interval_buckets);

    panel.querySelectorAll('[data-totals-field]').forEach(cell => {
        const value = data.totals[cell.dataset.totalsField];
        if (value !== undefined) cell.textContent = value;
    });

    const rollingNote = panel.querySelector('.clients-rolling-note');
    if (rollingNote) rollingNote.hidden = data.totals.log_records_dropped === 0;
    const zeroHint = panel.querySelector('.clients-zero-hint');
    if (zeroHint) zeroHint.hidden = summary.total_clients !== 0;

    if (data.table_enabled) {
        updateClientsTable(panel, data);
    }
}

function setClientsField(panel, field, value) {
    const element = panel.querySelector(`[data-clients-field="${field}"]`);
    if (element) element.textContent = value;
}

/**
 * Redraw one bucket group's counts and text bars.
 *
 * @param {Element} panel - The .clients-section element
 * @param {string} group - Bucket group name ("last_seen" or "poll_interval")
 * @param {Object} buckets - Bucket name to count
 */
function updateBuckets(panel, group, buckets) {
    const counts = Object.values(buckets);
    const scale = Math.max(...counts, 0);
    for (const [bucket, count] of Object.entries(buckets)) {
        const bar = panel.querySelector(
            `[data-bucket-group="${group}"][data-bucket="${CSS.escape(bucket)}"]`);
        if (bar) bar.textContent = bucketBar(count, scale);
        const counter = panel.querySelector(
            `[data-bucket-group="${group}-count"][data-bucket="${CSS.escape(bucket)}"]`);
        if (counter) counter.textContent = count;
    }
}

/**
 * Ten-cell text bar, matching the server's rendering exactly.
 *
 * @param {number} count - This bucket's count
 * @param {number} scale - The largest count in the group
 * @returns {string} Bar string
 */
function bucketBar(count, scale) {
    const CELLS = 10;
    if (scale <= 0 || count <= 0) return '░'.repeat(CELLS);
    const filled = Math.max(1, Math.round(count / scale * CELLS));
    return '█'.repeat(filled) + '░'.repeat(CELLS - filled);
}

/**
 * Rebuild the per-client table body from the API's display strings.
 *
 * textContent only: client addresses are third-party data.
 *
 * @param {Element} panel - The .clients-section element
 * @param {Object} data - /api/clients response with status "ok"
 */
function updateClientsTable(panel, data) {
    const tbody = panel.querySelector('.clients-tbody');
    if (!tbody) return;

    tbody.innerHTML = '';
    if (data.clients.length === 0) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.className = 'clients-table-empty';
        cell.colSpan = 6;
        cell.textContent = 'No clients to list';
        row.appendChild(cell);
        tbody.appendChild(row);
    }
    data.clients.forEach(client => {
        const row = document.createElement('tr');
        row.className = 'client-row';
        const cells = [
            ['client-address', client.address],
            ['client-ntp-hits', client.ntp_hits],
            ['client-ntp-drops', client.ntp_drops],
            ['client-interval', client.poll_display],
            ['client-last-seen', client.last_seen_display],
            ['client-nts-ke', client.nts_ke_display],
        ];
        for (const [className, value] of cells) {
            const cell = document.createElement('td');
            cell.className = className;
            cell.textContent = value;
            row.appendChild(cell);
        }
        tbody.appendChild(row);
    });

    const more = panel.querySelector('.clients-more');
    if (more) {
        more.hidden = data.clients_truncated === 0;
        more.textContent = `${data.clients_truncated} more clients beyond this list`;
    }
}

/**
 * Update the dashboard with fresh data from the API.
 *
 * Rows are matched to sources by address. The table itself is rendered by
 * the server, so when the set of sources changes (one added or removed, or
 * chronyd coming back after the page loaded without it) only a reload can
 * redraw it. Addresses are not guaranteed unique (two refclocks can share a
 * refid), so rows sharing one are paired with sources in table order.
 *
 * @param {Object} data - API response data
 */
function updateDashboard(data) {
    if (!Array.isArray(data.sources)) return;

    const rowElements = [...document.querySelectorAll('.source-row[data-address]')];
    const addressKey = addresses => [...addresses].sort().join('\n');
    const sameSources = addressKey(rowElements.map(row => row.dataset.address))
        === addressKey(data.sources.map(source => source.address));
    if (!sameSources) {
        window.location.reload();
        return;
    }

    const rows = new Map();
    rowElements.forEach(row => {
        const address = row.dataset.address;
        if (!rows.has(address)) rows.set(address, []);
        rows.get(address).push(row);
    });

    data.sources.forEach(source => {
        const row = rows.get(source.address).shift();

        // Update data attributes for countdowns
        const pollCell = row.querySelector('.poll');
        if (pollCell) {
            pollCell.dataset.pollInterval = source.poll;
            pollCell.dataset.lastRxTime = source.last_rx_timestamp;
        }

        // Update data attributes for time-since
        const lastRxCell = row.querySelector('.last-rx');
        if (lastRxCell) {
            lastRxCell.dataset.timestamp = source.last_rx_timestamp;
        }

        updateSourceName(row, source);

        row.classList.remove(...SOURCE_STATE_CLASSES);
        if (source.row_class) {
            row.classList.add(source.row_class);
        }

        const state = row.querySelector('.state');
        if (state) {
            state.textContent = source.state;
        }

        const latestMeas = row.querySelector('.latest-meas span');
        if (latestMeas) {
            latestMeas.textContent = source.latest_meas_display;
            latestMeas.className = source.latest_meas >= 0 ? 'offset-positive' : 'offset-negative';
        }

        const measErr = row.querySelector('.meas-err');
        if (measErr) {
            measErr.textContent = source.latest_meas_err_display;
        }

        updateReachabilityVisual(row, source.reachability_bits);
    });

    // Only the name is live here: the rest of this table is as rendered.
    const sources = new Map(data.sources.map(source => [source.address, source]));
    document.querySelectorAll('.stats-row[data-address]').forEach(row => {
        const source = sources.get(row.dataset.address);
        if (source) updateSourceName(row, source);
    });
}

/**
 * Show a source's current name in one of its table rows.
 *
 * @param {Element} row - Table row element
 * @param {Object} source - Source from the API
 */
function updateSourceName(row, source) {
    // textContent: PTR records are third-party data.
    const name = row.querySelector('.address .source-name');
    if (!name) return;

    name.textContent = source.display_name;
    if (source.hostname) {
        name.title = source.address;
    } else {
        name.removeAttribute('title');
    }
}

/**
 * Update the reachability visual indicator.
 *
 * @param {Element} row - Table row element
 * @param {boolean[]} bits - Poll outcomes from the API, newest first
 */
function updateReachabilityVisual(row, bits) {
    const reachCell = row.querySelector('.reach');
    if (!reachCell) return;

    const visual = reachCell.querySelector('.reach-visual');
    if (!visual) return;

    // Clear existing bits
    visual.innerHTML = '';

    // Oldest on the left, matching the server-rendered table.
    [...bits].reverse().forEach(bit => {
        const span = document.createElement('span');
        span.className = `reach-bit ${bit ? 'success' : 'failure'}`;
        visual.appendChild(span);
    });
}

/**
 * Show a warning that data may be stale.
 */
function showStaleWarning() {
    let warning = document.querySelector('.stale-warning');
    if (!warning) {
        warning = document.createElement('div');
        warning.className = 'stale-warning';
        warning.textContent = 'Unable to refresh data. Displayed values may be stale.';
        const header = document.querySelector('.dashboard-header');
        if (header) {
            header.parentNode.insertBefore(warning, header.nextSibling);
        }
    }
    warning.style.display = 'block';
}

/**
 * Hide the stale data warning.
 */
function hideStaleWarning() {
    const warning = document.querySelector('.stale-warning');
    if (warning) {
        warning.style.display = 'none';
    }
}

// Initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', initDashboard);
