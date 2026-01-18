# Tasks: Pychrony Dashboard Integration

**Input**: Design documents from `/specs/002-pychrony-integration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Integration tests explicitly requested in spec (FR-009, FR-010, FR-011). Unit tests included per constitution development workflow.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/second_hand/`, `tests/` at repository root
- Based on plan.md project structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add pychrony dependency and create service layer structure

- [ ] T001 Add pychrony dependency with Test PyPI source in pyproject.toml
- [ ] T002 [P] Create services directory with __init__.py in src/second_hand/services/__init__.py
- [ ] T003 [P] Create formatting utilities module in src/second_hand/utils/__init__.py
- [ ] T004 Run `uv sync` to install pychrony from Test PyPI

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core service and utilities that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Implement ChronyData dataclass in src/second_hand/services/chrony.py
- [ ] T006 Implement fetch_chrony_data() function with error handling in src/second_hand/services/chrony.py
- [ ] T007 [P] Implement format_offset() helper in src/second_hand/utils/__init__.py
- [ ] T008 [P] Implement format_duration() helper in src/second_hand/utils/__init__.py
- [ ] T009 [P] Implement format_reachability() helper in src/second_hand/utils/__init__.py
- [ ] T010 Create unit test for chrony service in tests/unit/__init__.py and tests/unit/test_chrony_service.py

**Checkpoint**: Foundation ready - chrony service fetches data and handles errors

---

## Phase 3: User Story 1 - View Time Synchronization Status (Priority: P1) 🎯 MVP

**Goal**: Display sync status, offset, stratum, and reference source in stat boxes

**Independent Test**: Load dashboard, verify tracking status boxes display correctly with sync indicator

### Tests for User Story 1

- [ ] T011 [P] [US1] Create unit test for tracking component in tests/unit/test_tracking_component.py

### Implementation for User Story 1

- [ ] T012 [US1] Create tracking_section component in src/second_hand/components/tracking.py
- [ ] T013 [US1] Create error_banner component in src/second_hand/components/error.py
- [ ] T014 [US1] Update dashboard.py to call fetch_chrony_data() and render tracking section in src/second_hand/components/dashboard.py
- [ ] T015 [US1] Add CSS styles for stat boxes and error banner in src/static/css/dashboard.css

**Checkpoint**: Dashboard shows sync status, offset, stratum, reference - handles connection errors gracefully

---

## Phase 4: User Story 2 - View NTP Sources List (Priority: P2)

**Goal**: Display table of all NTP sources with address, state, stratum, poll, reachability

**Independent Test**: Load dashboard, verify sources table shows all configured sources with correct styling

### Tests for User Story 2

- [ ] T016 [P] [US2] Create unit test for sources component in tests/unit/test_sources_component.py

### Implementation for User Story 2

- [ ] T017 [US2] Create sources_table component in src/second_hand/components/sources.py
- [ ] T018 [US2] Update dashboard.py to render sources section in src/second_hand/components/dashboard.py
- [ ] T019 [US2] Add CSS styles for sources table (selected row highlight, dimmed unreachable) in src/static/css/dashboard.css

**Checkpoint**: Dashboard shows sources table with visual distinction for selected/unreachable sources

---

## Phase 5: User Story 3 - View Source Statistics (Priority: P3)

**Goal**: Display table of source statistics with samples, offset, std dev, skew

**Independent Test**: Load dashboard, verify stats table shows sample counts and offset values

### Tests for User Story 3

- [ ] T020 [P] [US3] Create unit test for stats component in tests/unit/test_stats_component.py

### Implementation for User Story 3

- [ ] T021 [US3] Create stats_table component in src/second_hand/components/stats.py
- [ ] T022 [US3] Update dashboard.py to render stats section in src/second_hand/components/dashboard.py
- [ ] T023 [US3] Add CSS styles for stats table in src/static/css/dashboard.css

**Checkpoint**: Dashboard shows source statistics table

---

## Phase 6: User Story 4 - View RTC Data (Priority: P4)

**Goal**: Display RTC offset, drift, samples or "not configured" message

**Independent Test**: Load dashboard, verify RTC section shows data or "not configured" message

### Tests for User Story 4

- [ ] T024 [P] [US4] Create unit test for RTC component in tests/unit/test_rtc_component.py

### Implementation for User Story 4

- [ ] T025 [US4] Create rtc_section component in src/second_hand/components/rtc.py
- [ ] T026 [US4] Update dashboard.py to render RTC section in src/second_hand/components/dashboard.py
- [ ] T027 [US4] Add CSS styles for RTC section in src/static/css/dashboard.css

**Checkpoint**: Dashboard shows RTC data or "not configured" message

---

## Phase 7: Integration Testing Infrastructure

**Purpose**: Docker Compose setup for integration tests with real chronyd

- [ ] T028 Create docker/ directory structure
- [ ] T029 [P] Create chrony.conf for testing in docker/chrony.conf
- [ ] T030 [P] Create Dockerfile.test with chronyd and pychrony in docker/Dockerfile.test
- [ ] T031 Create docker-compose.test.yml with test services in docker/docker-compose.test.yml
- [ ] T032 Create integration test directory in tests/integration/__init__.py
- [ ] T033 Create integration test conftest with fixtures in tests/integration/conftest.py
- [ ] T034 [P] Create integration test for tracking data in tests/integration/test_chrony_integration.py
- [ ] T035 [P] Create integration test for sources data in tests/integration/test_chrony_integration.py
- [ ] T036 [P] Create integration test for source stats data in tests/integration/test_chrony_integration.py
- [ ] T037 Update CI workflow with integration test job in .github/workflows/ci.yml

**Checkpoint**: Integration tests pass in Docker with running chronyd

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [ ] T038 Update CI workflow branch patterns to include 002-* branches in .github/workflows/ci.yml
- [ ] T039 Run all unit tests locally and fix any failures
- [ ] T040 Run integration tests locally via Docker Compose
- [ ] T041 Run ruff format and ruff check
- [ ] T042 Run ty type checking
- [ ] T043 Validate dashboard loads within 2 seconds (SC-001)
- [ ] T044 Verify all existing tests still pass (SC-006)
- [ ] T045 Run quickstart.md validation steps

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Integration Testing (Phase 7)**: Can start after US1 complete (needs working dashboard)
- **Polish (Phase 8)**: Depends on all user stories and integration testing complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - No dependencies on other stories

### Within Each User Story

- Tests SHOULD be written first (TDD approach for components)
- Component before dashboard integration
- Dashboard integration before CSS
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (T007, T008, T009)
- All user story tests marked [P] can run in parallel
- Once Foundational phase completes, all user stories can start in parallel

---

## Parallel Example: User Story 1

```bash
# Launch tests for User Story 1:
Task: "Create unit test for tracking component in tests/unit/test_tracking_component.py"

# Then implement in sequence:
Task: "Create tracking_section component in src/second_hand/components/tracking.py"
Task: "Create error_banner component in src/second_hand/components/error.py"
Task: "Update dashboard.py to call fetch_chrony_data() and render tracking section"
Task: "Add CSS styles for stat boxes and error banner"
```

## Parallel Example: Foundational Utilities

```bash
# These can all run at the same time:
Task: "Implement format_offset() helper in src/second_hand/utils/__init__.py"
Task: "Implement format_duration() helper in src/second_hand/utils/__init__.py"
Task: "Implement format_reachability() helper in src/second_hand/utils/__init__.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test dashboard with tracking section
5. Deploy/demo if ready - shows sync status and error handling

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → MVP!
3. Add User Story 2 → Sources table visible
4. Add User Story 3 → Stats table visible
5. Add User Story 4 → RTC section visible
6. Add Integration Tests → CI validation
7. Polish → Ready for PR

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 + User Story 2
   - Developer B: User Story 3 + User Story 4
   - Developer C: Integration Testing Infrastructure
3. All merge and validate together in Polish phase

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing (TDD)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- pychrony models are used directly - no custom data models needed beyond ChronyData wrapper
