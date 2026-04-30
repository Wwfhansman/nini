# Repository Guidelines

## Project Structure & Module Organization

This repository currently contains the planning and contributor documents for **Nini Kitchen Agent**. The intended implementation layout is:

- `backend/`: FastAPI service, SQLite access, agent runtime, skills, providers, and tests.
- `frontend/`: final React/Vite kitchen terminal UI.
- `frontend-test/` or `/test-console`: temporary backend test console before final UI work.
- `docs/`: product, architecture, API, data model, provider, and delivery plans.
- `.env.example`: required environment variable template.

Follow `docs/12-development-plan.md` and `docs/14-implementation-checklist.md` when adding code.

## Build, Test, and Development Commands

No app runtime exists yet. Once implementation starts, use these expected commands:

```bash
./.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

Runs the FastAPI backend locally. Use the project virtualenv so WebSocket dependencies such as `websockets` are available.

```bash
pytest backend/tests
```

Runs backend tests.

```bash
cd frontend && npm install && npm run dev
```

Runs the final frontend once created.

Before code exists, validate docs with:

```bash
rg --files
```

## Coding Style & Naming Conventions

Use Python 3 with 4-space indentation, type hints, and Pydantic schemas for API and agent data contracts. Keep backend modules small and aligned with the planned paths: `agent/`, `skills/`, `terminal/`, `speech/`, and `mocks/`.

Use React component names in `PascalCase` such as `CookingView.jsx`; utilities and API clients use `camelCase` or concise lowercase filenames like `api.js`.

## Testing Guidelines

Backend tests should live under `backend/tests/` and use `test_*.py` names. Prioritize tests for state machine commands, schema validation, memory/inventory writes, and mock demo flow. Every P0 control command must verify `model_called=false`.

## Commit & Pull Request Guidelines

Current history uses conventional-style commits, for example:

```text
docs: initialize Nini Kitchen Agent plan
```

Prefer `docs:`, `feat:`, `fix:`, `test:`, and `chore:` prefixes. PRs should include a short summary, verification steps, affected docs, screenshots for UI changes, and notes on mock/hybrid/real provider behavior.

## Security & Configuration Tips

Never commit `.env`, API keys, SQLite databases, logs, or generated media. Keep secrets in local `.env` based on `.env.example`. All external providers must support `DEMO_MODE=mock` fallback so the demo remains reproducible without credentials.

## Agent-Specific Instructions

Develop backend first, then the temporary test console, then real providers, and only then the final frontend. Do not place business logic in the frontend. The backend is the source of truth for terminal state, tool events, memory, and inventory.
