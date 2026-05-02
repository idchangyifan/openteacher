# Development Setup

This workspace uses bundled Codex runtimes for local development.

## Installed Locally

- Python virtual environment: `backend/.venv`
- Backend dependencies: installed with `pip install -e ".[dev]"`
- Project-local pnpm: `tools/pnpm`
- Frontend dependencies: `frontend/node_modules`

## Useful Commands

Run backend tests and lint:

```powershell
.\scripts\test-backend.ps1
```

Build the frontend:

```powershell
.\scripts\build-frontend.ps1
```

Start the backend API:

```powershell
.\scripts\dev-backend.ps1
```

Start the frontend app:

```powershell
.\scripts\dev-frontend.ps1
```

The frontend runs on `http://localhost:5173` and proxies API calls to `http://localhost:8000`.

## PostgreSQL

If Docker is available, start PostgreSQL with:

```powershell
docker compose up -d postgres
```

The default connection string is in `.env.example`.

## Docker on Windows

Docker Desktop and WSL are expected for Linux containers.

Useful checks:

```powershell
docker --version
docker compose version
docker info
```

If Windows optional features were just enabled, restart Windows once, then run:

```powershell
.\scripts\finish-docker-setup.ps1
```

That script starts Docker Desktop, waits for the engine, and starts the project PostgreSQL container.

### Current Machine Note

On this Windows Server workspace, Docker Desktop and WSL are installed, but Linux containers cannot start because Hyper-V cannot be installed. The server reports that the processor does not expose the required virtualization capabilities, so Docker's `desktop-linux` engine returns HTTP 500 and the PostgreSQL container cannot run here.

The project can still run the Python backend and React frontend locally. PostgreSQL needs either a machine with Hyper-V/WSL2 support, a remote PostgreSQL instance, or a native PostgreSQL install on this machine.
