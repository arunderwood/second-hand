<!--
SYNC IMPACT REPORT
==================
Version change: N/A (initial) → 1.0.0
Modified principles: N/A (initial creation)
Added sections:
  - Core Principles (5 principles)
  - Technical Constraints
  - Development Workflow
  - Governance
Removed sections: None
Templates requiring updates:
  - .specify/templates/plan-template.md ✅ (compatible - Constitution Check section exists)
  - .specify/templates/spec-template.md ✅ (compatible - no changes needed)
  - .specify/templates/tasks-template.md ✅ (compatible - security hardening task exists)
Follow-up TODOs: None
-->

# second-hand Constitution

## Core Principles

### I. Security First (NON-NEGOTIABLE)

All code MUST be secure and MUST NOT introduce vulnerabilities to the infrastructure it runs on.

- **Input Validation**: All external inputs (API requests, configuration) MUST be validated and sanitized
- **No Command Injection**: User-controlled data MUST NEVER be passed to shell commands or system calls
- **Dependency Security**: Dependencies MUST be pinned to specific versions; security updates MUST be applied promptly
- **Least Privilege**: The application MUST run with minimal required permissions
- **No Secrets in Code**: Credentials, API keys, and sensitive configuration MUST NEVER be hardcoded
- **OWASP Compliance**: Code MUST avoid OWASP Top 10 vulnerabilities

**Rationale**: This project runs on homelab infrastructure. A security breach could compromise the entire network.

### II. Lightweight Design

The application MUST maintain a small footprint on the system it runs on.

- **Minimal Dependencies**: Only include dependencies that are strictly necessary
- **Resource Efficiency**: Memory usage SHOULD remain under 100MB during normal operation
- **No Background Polling Abuse**: Data refresh intervals MUST be configurable and default to reasonable values (not aggressive polling)
- **Single Process**: Prefer a single-process architecture over multi-process/worker pools unless absolutely necessary

**Rationale**: This is a monitoring tool for a homelab; it should not become a burden on the system it monitors.

### III. Simple Setup

Installation and configuration MUST be straightforward for homelab users.

- **Single Command Install**: Installation SHOULD be achievable with minimal steps (ideally pip install or docker run)
- **Sensible Defaults**: The application MUST work out-of-the-box with reasonable defaults
- **Configuration Over Code**: All customization MUST be achievable through configuration files or environment variables
- **Clear Error Messages**: Configuration errors MUST produce actionable error messages

**Rationale**: Homelab projects should be easy to deploy without extensive documentation reading.

### IV. Focused Scope

second-hand is a dashboard for chrony statistics visualization only.

- **Single Purpose**: The application displays chrony server statistics; it does NOT configure chrony
- **Read-Only**: All interactions with chrony MUST be read-only queries via pychrony
- **No Feature Creep**: Reject features that fall outside the core purpose of displaying chrony statistics
- **pychrony Integration**: Use the pychrony library for all chrony communication

**Rationale**: A focused tool is easier to maintain, secure, and understand.

### V. Learning-Friendly Code

Code SHOULD be clear and educational since this is a learning project.

- **Readable Over Clever**: Prefer straightforward implementations over clever optimizations
- **Meaningful Names**: Variables, functions, and classes MUST have descriptive names
- **Structured Logging**: Use structured logging to aid debugging and learning
- **Type Hints**: Python code SHOULD include type hints for clarity

**Rationale**: This is a learning opportunity project; the codebase should teach good practices.

## Technical Constraints

**Language/Version**: Python 3.11+
**Framework**: FastAPI
**Core Dependency**: pychrony (https://github.com/arunderwood/pychrony)
**Deployment**: Single-process ASGI server (uvicorn)
**Configuration**: Environment variables and/or YAML/TOML config file

**Prohibited**:
- Subprocess calls with user-controlled input
- eval() or exec() with external data
- Storing secrets in source code or version control
- Heavy frameworks or ORMs (keep it simple)

## Development Workflow

**Code Changes**:
1. All changes MUST pass security review (manual check for injection vulnerabilities)
2. New dependencies MUST be justified against Principle II (Lightweight Design)
3. New features MUST align with Principle IV (Focused Scope)

**Testing**:
- Unit tests for business logic
- Integration tests for API endpoints
- Security-focused tests for input validation

**Documentation**:
- README MUST include setup instructions
- Configuration options MUST be documented

## Governance

**Constitution Authority**: This constitution supersedes all other project practices. When in conflict, principles take precedence in order (I > II > III > IV > V).

**Amendment Process**:
1. Proposed changes MUST be documented with rationale
2. Security-related changes (Principle I) require explicit security impact analysis
3. Version bumps follow semantic versioning:
   - MAJOR: Principle removal or backward-incompatible redefinition
   - MINOR: New principle or significant expansion
   - PATCH: Clarifications and wording improvements

**Compliance**:
- All pull requests MUST verify compliance with these principles
- Security violations are blocking; other violations require documented justification

**Version**: 1.0.0 | **Ratified**: 2026-01-17 | **Last Amended**: 2026-01-17
