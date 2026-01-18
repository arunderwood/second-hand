# Tasks: Dashboard Initialization

**Input**: Design documents from `/specs/001-dashboard-init/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per spec requirement (FR-005: "System MUST include a unit test framework with initial example tests")

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:
- **Source**: `src/second_hand/`
- **Components**: `src/second_hand/components/`
- **Static**: `src/static/css/`
- **Tests**: `tests/`
- **GitHub**: `.github/`

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create project structure and configure tooling

- [ ] T001 Create directory structure per plan.md: src/second_hand/, src/second_hand/components/, src/static/css/, tests/
- [ ] T002 Create pyproject.toml with dependencies: fastapi, uvicorn, htpy, pydantic-settings, pytest, pytest-cov, httpx
- [ ] T003 [P] Create src/second_hand/__init__.py with version metadata
- [ ] T004 [P] Create tests/__init__.py
- [ ] T005 [P] Configure ruff in pyproject.toml (linting and formatting)
- [ ] T006 [P] Configure ty in pyproject.toml (type checking)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T007 Implement Settings model with pydantic-settings in src/second_hand/config.py
- [ ] T008 Create base FastAPI application in src/second_hand/main.py (empty routes, static mount)
- [ ] T009 [P] Create tests/conftest.py with pytest fixtures (test client, settings)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - View Dashboard Landing Page (Priority: P1) MVP

**Goal**: Serve a modern, visually sharp dashboard page with placeholder content for chrony statistics

**Independent Test**: Start server with `uvicorn second_hand.main:app`, navigate to http://localhost:8000, see styled dashboard

### Tests for User Story 1

- [ ] T010 [P] [US1] Create test for base layout component in tests/test_components.py
- [ ] T011 [P] [US1] Create test for dashboard page component in tests/test_components.py
- [ ] T012 [P] [US1] Create test for GET / endpoint returns 200 with HTML in tests/test_main.py

### Implementation for User Story 1

- [ ] T013 [P] [US1] Create base layout htpy component in src/second_hand/components/__init__.py
- [ ] T014 [P] [US1] Create base layout htpy component in src/second_hand/components/base.py
- [ ] T015 [US1] Create dashboard page htpy component in src/second_hand/components/dashboard.py
- [ ] T016 [US1] Implement GET / route returning dashboard HTML in src/second_hand/main.py
- [ ] T017 [US1] Create responsive CSS with modern, sharp styling in src/static/css/style.css
- [ ] T018 [US1] Add health check endpoint GET /health in src/second_hand/main.py

**Checkpoint**: Dashboard displays at http://localhost:8000 with placeholder content and responsive styling

---

## Phase 4: User Story 2 - Develop with Immediate Feedback (Priority: P2)

**Goal**: Enable hot-reload development mode for rapid iteration

**Independent Test**: Run `uvicorn second_hand.main:app --reload`, modify a component file, refresh browser to see changes

### Implementation for User Story 2

- [ ] T019 [US2] Verify uvicorn --reload works with htpy components (manual test, document in quickstart)
- [ ] T020 [US2] Add dev mode instructions to pyproject.toml scripts section
- [ ] T021 [US2] Create test for production vs development mode configuration in tests/test_config.py

**Checkpoint**: Code changes reflect in browser after refresh without server restart

---

## Phase 5: User Story 3 - Run Automated Tests (Priority: P3)

**Goal**: pytest framework with example tests that run locally and in CI

**Independent Test**: Run `pytest` and see all tests pass with coverage report

### Implementation for User Story 3

- [ ] T022 [P] [US3] Create GitHub Actions CI workflow in .github/workflows/ci.yml
- [ ] T023 [P] [US3] Configure pytest-cov in pyproject.toml for coverage reporting
- [ ] T024 [US3] Add ty type checking step to CI workflow in .github/workflows/ci.yml
- [ ] T025 [US3] Add Python version matrix (3.14, 3.13, 3.12) to CI workflow

**Checkpoint**: `pytest` passes locally; CI runs tests on push with type checking

---

## Phase 6: User Story 4 - Onboard as New Contributor (Priority: P4)

**Goal**: README with project mission and concise getting started steps

**Independent Test**: Clone repo, follow README, see dashboard running in under 5 minutes

### Implementation for User Story 4

- [ ] T026 [P] [US4] Create README.md with project mission and overview
- [ ] T027 [P] [US4] Add Getting Started section to README.md (prerequisites, install, run)
- [ ] T028 [US4] Add Development section to README.md (dev mode, testing, linting)
- [ ] T029 [US4] Create .github/dependabot.yml for daily Python updates (no PR limit)

**Checkpoint**: New contributor can follow README and have dashboard running

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [ ] T030 Run ty type checking on entire codebase: `ty check src/`
- [ ] T031 Run ruff linting and formatting: `ruff check . && ruff format .`
- [ ] T032 Verify all tests pass with coverage: `pytest --cov=second_hand`
- [ ] T033 Validate quickstart.md checklist against actual project
- [ ] T034 Test responsive design at 320px, 768px, 1920px viewport widths

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational - Uses US1 components for testing
- **User Story 3 (P3)**: Can start after Foundational - Tests US1 in CI
- **User Story 4 (P4)**: Can start after Foundational - Documents US1-3

### Within Each User Story

- Tests FIRST (T010-T012 before T013-T018)
- Components before routes
- Routes before styling
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**:
```
T003, T004, T005, T006 can run in parallel
```

**Phase 2 (Foundational)**:
```
T009 can run in parallel with T007, T008
```

**Phase 3 (US1 - Dashboard)**:
```
T010, T011, T012 can run in parallel (tests)
T013, T014 can run in parallel (components)
```

**Phase 5 (US3 - Testing)**:
```
T022, T023 can run in parallel
```

**Phase 6 (US4 - Documentation)**:
```
T026, T027 can run in parallel
```

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Create test for base layout component in tests/test_components.py"
Task: "Create test for dashboard page component in tests/test_components.py"
Task: "Create test for GET / endpoint returns 200 with HTML in tests/test_main.py"

# Launch component scaffolding together:
Task: "Create base layout htpy component in src/second_hand/components/__init__.py"
Task: "Create base layout htpy component in src/second_hand/components/base.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Dashboard)
4. **STOP and VALIDATE**: Dashboard displays at http://localhost:8000
5. Can demo/deploy immediately

### Incremental Delivery

1. Setup + Foundational → Project runs (empty)
2. Add User Story 1 → Dashboard visible → **MVP Complete**
3. Add User Story 2 → Dev mode verified
4. Add User Story 3 → CI running, tests passing
5. Add User Story 4 → README complete, ready for contributors

### Recommended Execution

For solo developer:
1. T001-T009 (Setup + Foundational)
2. T010-T018 (US1 - Dashboard) - **MVP milestone**
3. T019-T021 (US2 - Dev mode)
4. T022-T025 (US3 - CI/Testing)
5. T026-T029 (US4 - Documentation)
6. T030-T034 (Polish)

---

## Notes

- [P] tasks = different files, no dependencies within same phase
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- htpy components enable type-safe testing without regex
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
