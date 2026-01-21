/**
 * Dashboard JavaScript Module
 *
 * Provides real-time countdown animations and auto-refresh functionality
 * for the second-hand NTP dashboard.
 *
 * Features:
 * - Poll countdown timers updating every second
 * - "Time since last receive" display updating every second
 * - Auto-refresh of data every 30 seconds
 * - Progressive enhancement (works without JS)
 */

// Configuration (matches server-side defaults)
const REFRESH_INTERVAL_MS = 30000; // 30 seconds
const UPDATE_INTERVAL_MS = 1000; // 1 second

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

    // Start the 30-second data refresh interval
    refreshIntervalId = setInterval(refreshData, REFRESH_INTERVAL_MS);

    // Run initial update
    updateTimers();

    console.log('Dashboard initialized with real-time updates');
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
        const interval = parseInt(cell.dataset.pollInterval, 10);
        const lastRx = parseInt(cell.dataset.lastRxTime, 10);

        if (isNaN(interval) || isNaN(lastRx)) return;

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
 * Called every 30 seconds.
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
 * @param {Object} data - API response data
 */
function updateDashboard(data) {
    if (!data.sources || !Array.isArray(data.sources)) return;

    const rows = document.querySelectorAll('.source-row');

    data.sources.forEach((source, index) => {
        if (index >= rows.length) return;

        const row = rows[index];

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

        // Update state class
        row.classList.remove('source-selected', 'source-falseticker', 'source-jittery', 'source-unreachable');
        if (source.is_selected) {
            row.classList.add('source-selected');
        } else if (source.state === 'Falseticker') {
            row.classList.add('source-falseticker');
        } else if (source.state === 'Jittery') {
            row.classList.add('source-jittery');
        } else if (source.reachability === 0) {
            row.classList.add('source-unreachable');
        }

        // Update measurement values
        const latestMeas = row.querySelector('.latest-meas span');
        if (latestMeas) {
            latestMeas.textContent = formatOffset(source.latest_meas);
            latestMeas.className = source.latest_meas >= 0 ? 'offset-positive' : 'offset-negative';
        }

        const measErr = row.querySelector('.meas-err');
        if (measErr) {
            measErr.textContent = formatOffset(source.latest_meas_err);
        }

        // Update reachability visual
        updateReachabilityVisual(row, source.reachability);
    });
}

/**
 * Format an offset value for display.
 *
 * @param {number} seconds - Offset in seconds
 * @returns {string} Formatted offset with appropriate unit
 */
function formatOffset(seconds) {
    const absVal = Math.abs(seconds);
    const sign = seconds >= 0 ? '+' : '-';

    if (absVal >= 1) {
        return `${sign}${absVal.toFixed(3)} s`;
    } else if (absVal >= 0.001) {
        return `${sign}${(absVal * 1000).toFixed(3)} ms`;
    } else if (absVal >= 0.000001) {
        return `${sign}${(absVal * 1000000).toFixed(1)} \u00b5s`;
    } else {
        return `${sign}${Math.round(absVal * 1000000000)} ns`;
    }
}

/**
 * Update the reachability visual indicator.
 *
 * @param {Element} row - Table row element
 * @param {number} reachability - Reachability register value (0-255)
 */
function updateReachabilityVisual(row, reachability) {
    const reachCell = row.querySelector('.reach');
    if (!reachCell) return;

    const visual = reachCell.querySelector('.reach-visual');
    if (!visual) return;

    // Clear existing bits
    visual.innerHTML = '';

    // Add new bit indicators (MSB to LSB for left-to-right display)
    for (let i = 7; i >= 0; i--) {
        const bit = (reachability >> i) & 1;
        const span = document.createElement('span');
        span.className = `reach-bit ${bit ? 'success' : 'failure'}`;
        visual.appendChild(span);
    }
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
