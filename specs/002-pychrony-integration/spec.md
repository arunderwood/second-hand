# Feature Specification: Pychrony Dashboard Integration

**Feature Branch**: `002-pychrony-integration`
**Created**: 2026-01-17
**Status**: Draft
**Input**: User description: "Integrate pychrony into second-hand. uv should source the package from PyPI Test (https://test.pypi.org/simple/). All data sources that pychrony supports should be displayed on the dash. Just displaying tables of the data with single-attribute boxes for high value data is sufficient for now, any advanced functionality like graphing or trend tracking can happen later. Add integration tests to ensure the pychrony features are working. The integration tests will need to run in a framework like docker compose to ensure chronyd can be installed and started. Ensure the integration tests run in CI. Test all features locally before making a PR"

## Clarifications

### Session 2026-01-17

- Q: Should chrony data be fetched fresh on each page load or cached? → A: Fresh fetch on every page load, with architecture supporting easy migration to caching later
- Q: What should integration tests verify? → A: Connectivity + data structure validation (fields present, correct types)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Time Synchronization Status (Priority: P1)

A system administrator visits the second-hand dashboard to check the current time synchronization status of their server. They see at-a-glance high-value metrics like current offset, stratum level, and whether the system is synchronized.

**Why this priority**: This is the core value proposition - understanding if time synchronization is healthy. Without this, the dashboard provides no useful information.

**Independent Test**: Can be fully tested by loading the dashboard and verifying tracking status displays correctly. Delivers immediate value by showing synchronization health.

**Acceptance Scenarios**:

1. **Given** chronyd is running and synchronized, **When** the user visits the dashboard, **Then** they see the current offset, stratum, reference source name, and a "synchronized" indicator
2. **Given** chronyd is running but not synchronized, **When** the user visits the dashboard, **Then** they see an "unsynchronized" indicator with the current stratum (16)
3. **Given** chronyd is not accessible (not running or permission denied), **When** the user visits the dashboard, **Then** they see an error message indicating the connection issue

---

### User Story 2 - View NTP Sources List (Priority: P2)

A system administrator wants to see all configured NTP sources and their current states to verify which servers are being used for time synchronization.

**Why this priority**: Knowing which NTP sources are available and their states helps diagnose synchronization issues. Depends on basic connectivity established in P1.

**Independent Test**: Can be tested by displaying the sources table and verifying all configured sources appear with correct state information.

**Acceptance Scenarios**:

1. **Given** chronyd has multiple NTP sources configured, **When** the user views the sources section, **Then** they see a table with each source's address, stratum, state, poll interval, and reachability
2. **Given** one source is currently selected for synchronization, **When** the user views the sources table, **Then** the selected source is visually distinguished from other sources

---

### User Story 3 - View Source Statistics (Priority: P3)

A system administrator wants to examine the statistical quality of measurements from each NTP source to identify sources with poor performance.

**Why this priority**: Statistical data helps with advanced troubleshooting but is not essential for basic monitoring. Useful after understanding which sources exist.

**Independent Test**: Can be tested by displaying the source statistics table and verifying sample counts and offset values appear correctly.

**Acceptance Scenarios**:

1. **Given** chronyd has collected measurements from sources, **When** the user views the source statistics section, **Then** they see a table with each source's sample count, standard deviation, offset, and skew values

---

### User Story 4 - View RTC Data (Priority: P4)

A system administrator with RTC tracking enabled wants to monitor the hardware clock's drift relative to system time.

**Why this priority**: RTC data is optional (requires explicit configuration) and only relevant for systems with RTC tracking enabled. Low priority as many systems don't use this feature.

**Independent Test**: Can be tested by verifying RTC data displays when available, or shows appropriate message when unavailable.

**Acceptance Scenarios**:

1. **Given** RTC tracking is enabled in chronyd, **When** the user views the RTC section, **Then** they see the RTC offset, frequency offset, and calibration sample count
2. **Given** RTC tracking is not enabled, **When** the user views the RTC section, **Then** they see a message indicating RTC tracking is not available

---

### Edge Cases

- What happens when chronyd socket has restrictive permissions?
  - Display a clear "permission denied" error with guidance to add user to chrony group
- What happens when chronyd is not installed or not running?
  - Display a "connection failed" error indicating chronyd may not be running
- What happens when pychrony library fails to load (missing libchrony)?
  - Display an error indicating the library dependency issue
- What happens when chrony returns no sources?
  - Display an empty sources table with a message indicating no sources are configured

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display current time synchronization tracking status including offset, stratum, reference source, and leap status
- **FR-002**: System MUST display a list of all configured NTP sources with their address, stratum, state, poll interval, and reachability
- **FR-003**: System MUST display source statistics including sample count, offset, standard deviation, and skew for each source
- **FR-004**: System MUST display RTC data when available, or indicate when RTC tracking is not configured
- **FR-005**: System MUST handle connection errors gracefully with user-friendly error messages
- **FR-006**: System MUST highlight high-value metrics (offset, stratum, synchronization status) in prominent single-attribute boxes
- **FR-007**: System MUST present detailed data (sources, statistics) in readable tabular format
- **FR-008**: Package manager MUST source pychrony from PyPI Test (https://test.pypi.org/simple/)
- **FR-009**: Integration tests MUST run in a containerized environment with chronyd installed and running
- **FR-010**: Integration tests MUST be executed as part of the CI pipeline
- **FR-011**: Integration tests MUST verify chronyd connectivity and validate data structure correctness (fields present, correct types)

### Key Entities

- **TrackingStatus**: Current synchronization state - offset, stratum, reference source, leap status, frequency error, root delay/dispersion
- **Source**: An NTP time source - address, state (selected/unselected/falseticker), mode (client/peer/refclock), stratum, poll interval, reachability
- **SourceStats**: Measurement statistics per source - sample count, runs, span, standard deviation, offset, skew
- **RTCData**: Hardware clock data - reference time, calibration samples, offset, frequency drift

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dashboard loads and displays chrony data within 2 seconds when chronyd is accessible
- **SC-002**: All four pychrony data sources (tracking, sources, source stats, RTC) are displayed on the dashboard
- **SC-003**: High-value metrics are displayed in single-attribute boxes that are visible without scrolling
- **SC-004**: Error states are communicated clearly with actionable guidance
- **SC-005**: Integration tests pass in CI with a running chronyd instance in containers
- **SC-006**: All existing unit tests continue to pass after integration

## Assumptions

- Data is fetched fresh from chronyd on every page load (no caching); architecture should allow easy addition of caching layer later
- The pychrony package from PyPI Test provides stable bindings for the current version of libchrony
- Pre-built wheels for pychrony include libchrony, so no system-level library installation is required for the application
- Docker Compose is an acceptable integration test framework for CI
- The integration test container will use a Linux distribution where chronyd can be installed via package manager
- Users viewing the dashboard have network access to the server running second-hand
- Refresh/live updates are out of scope for this feature (manual page reload is acceptable)
