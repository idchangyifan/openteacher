# AGENTS.md

This file is the durable handoff memory for agent work on OpenTeacher. Read it before making changes.

## Project Mission

OpenTeacher is an open-source AI teacher project for students in under-resourced regions, especially children in rural and economically disadvantaged areas in China.

The goal is education equity: bring high-quality, rigorous, first-tier-city-level teaching to students who otherwise do not have access to it.

OpenTeacher should be a teacher, not merely a study companion. It should be warm, patient, strict, principled, and focused on helping students genuinely learn.

## Product Philosophy

- The agent is a teacher, not a friend, parent, therapist, or answer machine.
- It should be warm but demanding, patient but not indulgent, strict but never humiliating.
- It should teach reasoning and method, not just output answers.
- It should refuse pure answer-copying behavior and require student thinking.
- It should remember students with care: academic progress, common errors, learning behavior, and concrete progress.
- It must avoid unnecessary sensitive data about minors.

## Skill Ecosystem

The long-term project direction is an open teaching skill ecosystem.

Important idea:

- Excellent teachers should be able to contribute structured Teaching Skills that encode their teaching methods and style.
- Skills should not be only prompts. They should contain knowledge scope, diagnosis questions, common error patterns, correction strategies, practice policy, and safety boundaries.
- The project should support official skills, verified-teacher skills, community experimental skills, and private local skills.

Current sample skill:

- `skills/junior-math-linear-equation.yaml`

Current schema draft:

- `specs/teaching-skill.schema.yaml`

## Technical Stack

Current chosen stack:

- Backend: Python, FastAPI, SQLAlchemy, Alembic
- Frontend: React, TypeScript, Vite
- Relational database: PostgreSQL
- Memory module storage: undecided, behind a service interface
- RAG storage: undecided, behind a service interface

Current important service boundaries:

- `backend/app/services/agent_harness.py`
- `backend/app/services/memory.py`
- `backend/app/services/rag.py`
- `backend/app/services/skill_registry.py`

## Repository

GitHub repository:

- https://github.com/idchangyifan/openteacher

Default branch:

- `main`

Initial scaffold has been pushed.

## Environment Reality

The original Windows Server workspace can run Codex Desktop and edit code, but cannot run Docker Linux containers because the Windows Server itself is virtualized and does not expose nested virtualization.

Do not spend time trying to make Docker Desktop work on that Windows Server unless the host enables nested virtualization. The observed failure mode was:

- Docker CLI and Docker Desktop installed successfully.
- Docker engine returns HTTP 500.
- WSL2 distro creation fails with `HCS_E_HYPERV_NOT_INSTALLED`.
- Hyper-V role installation fails because the processor does not expose required virtualization capabilities.

The preferred development direction is now:

- Mac or local workstation for SSH/editor/browser.
- Remote Ubuntu server as the real development machine.
- Codex CLI on Ubuntu.
- Docker and all middleware on Ubuntu.

## Remote Ubuntu State

Remote Ubuntu host used during setup:

- Ubuntu 24.04 amd64
- SSH user was `root`
- mihomo installed and running as `mihomo.service`
- Codex CLI installed globally with npm
- Codex CLI version observed: `codex-cli 0.128.0`
- Codex login completed using ChatGPT

Mihomo state:

- Binary: `/usr/local/bin/mihomo`
- Config: `/etc/mihomo/config.yaml`
- Service: `mihomo.service`
- HTTP proxy: `127.0.0.1:7890`
- SOCKS proxy: `127.0.0.1:7891`
- Controller: `127.0.0.1:9090`

Proxy environment was configured globally on Ubuntu for common CLI tools:

- `/etc/profile.d/99-proxy.sh`
- `/etc/environment`
- apt proxy
- git proxy
- npm proxy
- pip proxy
- systemd manager default environment

The proxy is environment-variable based, not a transparent/TUN proxy. Do not assume every process automatically uses it unless it respects `HTTP_PROXY`/`HTTPS_PROXY`.

## How To Continue On Ubuntu

On Ubuntu:

```bash
git clone https://github.com/idchangyifan/openteacher.git
cd openteacher
codex
```

Backend setup target:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check app tests
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend setup target:

```bash
cd frontend
npm install
npm run build
npm run dev -- --host 127.0.0.1 --port 5173
```

Use SSH tunnels from Mac/local machine rather than exposing dev ports publicly:

```bash
ssh -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 root@<ubuntu-host>
```

Then open:

- http://127.0.0.1:5173
- http://127.0.0.1:8000/api/v1/health

## Current Next Steps

Recommended next steps:

1. Make Ubuntu the main development workspace.
2. Clone the GitHub repo on Ubuntu.
3. Verify backend tests and frontend build on Ubuntu.
4. Start PostgreSQL through Docker Compose on Ubuntu.
5. Add a proper `.env` and database migration flow.
6. Connect the mock `AgentHarness` to a real LLM provider.
7. Keep memory and RAG storage behind interfaces until the storage design is clearer.
8. Build the first real teaching loop around junior math equation solving.

## Development Style

- Preserve the project mission and teacher identity.
- Avoid turning the agent into a generic chatbot.
- Keep abstractions small and aligned with the current scaffold.
- Do not add many middlewares before the first teaching loop works.
- Prefer Docker Compose on Ubuntu for middleware.
- Keep secrets out of the repository.

