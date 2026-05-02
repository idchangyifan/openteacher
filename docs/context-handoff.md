# Context Handoff

This document captures the important context from the initial planning and environment setup work so future Codex sessions can continue without relying on chat history.

## Project Summary

OpenTeacher is an open-source AI teacher system for education equity. It is intended to help students in under-resourced regions get access to high-quality teaching.

The user wants the system to behave as a teacher, not merely a learning companion:

- warm but strict
- rigorous but never humiliating
- focused on reasoning, not answer dumping
- capable of remembering students with care
- extensible through teacher-authored skills

The project is not primarily intended to make money. The open-source ecosystem and public reputation value are more important than commercial monetization.

## Core Product Decisions

1. Support the full K-12 direction architecturally, but build one deep sample first.
2. Use skills for subjects, teaching tasks, and teacher styles.
3. Make Teaching Skills structured, reviewable, testable artifacts, not just prompt blobs.
4. Use a web app first because the user is more comfortable with web development.
5. Include a teacher/volunteer dashboard later.
6. Treat long-term student memory as a core differentiator.

## Current Scaffold

The repository contains:

- Python FastAPI backend scaffold
- React/Vite frontend scaffold
- PostgreSQL docker-compose service definition
- Teaching persona documentation
- Memory system documentation
- Skill authoring documentation
- Teaching skill schema draft
- Junior math linear equation sample skill
- Static prototype in `web/`

## Environment History

The first local workspace was a Windows Server VM.

Working on Windows:

- Python backend dependencies were installed in `backend/.venv`.
- Frontend dependencies were installed with project-local pnpm.
- Backend tests and lint passed.
- Frontend build passed.
- Git and GitHub CLI were installed.
- GitHub repo was created and pushed.

Not working on Windows:

- Docker Desktop could be installed.
- Docker CLI and Compose could be installed.
- But Linux containers could not run because the VM lacks nested virtualization.
- WSL2 could not create a VM.

Important failure signatures:

```text
Docker engine HTTP 500
HCS_E_HYPERV_NOT_INSTALLED
Hyper-V cannot be installed: The processor does not have required virtualization capabilities.
```

Conclusion:

Do not use the Windows Server as the main middleware host. Use Ubuntu for Docker.

## Ubuntu Setup History

The remote Ubuntu server was prepared for future development:

- Ubuntu 24.04 amd64 was confirmed.
- mihomo was installed as `/usr/local/bin/mihomo`.
- `/etc/mihomo/config.yaml` was populated from the user-provided subscription.
- `mihomo.service` was created and enabled.
- Proxy ports were restricted to localhost for safety:
  - HTTP `127.0.0.1:7890`
  - SOCKS `127.0.0.1:7891`
  - API `127.0.0.1:9090`
- Proxy test to Google and OpenAI succeeded.
- Environment proxy variables were configured globally for common tools.
- Node.js/npm were installed from Ubuntu apt packages.
- Codex CLI was installed with `npm install -g @openai/codex`.
- Codex CLI login was completed using ChatGPT.

## Security Notes

Sensitive values were provided during setup in chat, including a GitHub token, SSH password, and proxy subscription URL. They were not committed to the repository, but they should be rotated by the user.

Do not commit:

- OpenAI API keys
- GitHub tokens
- SSH passwords
- proxy subscriptions
- mihomo config files
- `.env` files

## Recommended Development Workflow

Use the remote Ubuntu server as the real development environment:

```bash
git clone https://github.com/idchangyifan/openteacher.git
cd openteacher
codex
```

Use Mac or another local machine only as:

- browser
- terminal
- editor via SSH / Remote SSH

Run middleware through Docker Compose on Ubuntu.

Use SSH tunnels for dev ports:

```bash
ssh -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 root@<ubuntu-host>
```

## Immediate Next Build Task

The next concrete engineering task should be:

1. Clone this repository on Ubuntu.
2. Install backend and frontend dependencies there.
3. Verify tests and build.
4. Start Postgres with Docker Compose.
5. Wire backend config to the running Postgres.
6. Add the first migration.

After that, begin integrating a real LLM provider into `AgentHarness`.

