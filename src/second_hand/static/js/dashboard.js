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

    // Run initial update
    updateTimers();

    console.log('Dashboard initialized with real-time updates');
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

        // textContent: PTR records are third-party data.
        const name = row.querySelector('.address .source-name');
        if (name) {
            name.textContent = source.display_name;
            if (source.hostname) {
                name.title = source.address;
            } else {
                name.removeAttribute('title');
            }
        }

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
