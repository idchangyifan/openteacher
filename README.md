# OpenTeacher

OpenTeacher is an open-source AI teacher project for students in under-resourced regions. The goal is to make high-quality, rigorous, warm teaching available to every child through an extensible agent harness, open teaching skills, and long-term student memory.

The project starts with a simple web prototype and grows toward a full AI teacher infrastructure:

- A teacher-like agent, not just a study companion
- Subject and grade skills written by educators
- Structured memory for student learning progress
- Teacher and volunteer dashboard support
- Open skill standards for community contribution

## Product Principles

1. Be a teacher.
   The agent should be warm, patient, demanding, and principled. It should not flatter students or simply provide answers.

2. Teach the method, not only the answer.
   The agent should diagnose where the student is stuck, guide step by step, and require the student to explain their thinking.

3. Remember with care.
   Memory should improve teaching quality without collecting unnecessary personal information.

4. Make great teaching reusable.
   Excellent teachers should be able to encode their teaching style and methods as reusable skills.

5. Build for public good.
   The project should be open, auditable, self-hostable, and friendly to schools, volunteers, and public-interest organizations.

## Current MVP

This repository currently contains:

- A Python backend scaffold in `backend/`
- A React frontend scaffold in `frontend/`
- A PostgreSQL local development service in `docker-compose.yml`
- A static web prototype in `web/`
- The first teaching skill schema in `specs/teaching-skill.schema.yaml`
- A sample junior math skill in `skills/junior-math-linear-equation.yaml`
- The teacher persona policy in `docs/teacher-persona.md`
- The first memory design in `docs/memory-system.md`
- A contribution model for educator-written skills in `docs/skill-authoring.md`

Open `web/index.html` in a browser to try the first prototype.

## Technology Stack

- Backend: Python, FastAPI, SQLAlchemy, Alembic
- Frontend: React, TypeScript, Vite
- Relational database: PostgreSQL
- Memory module storage: undecided, behind an interface
- RAG storage: undecided, behind an interface

## Project Structure

```text
backend/        Python API, agent harness, service interfaces
frontend/       React web app
docs/           Product and architecture notes
skills/         Teaching skill examples
specs/          Skill schema drafts
web/            Static prototype kept for quick local preview
```

## Local Development Target

The intended local development flow is:

```bash
docker compose up -d postgres
cd backend
python -m venv .venv
pip install -e ".[dev]"
uvicorn app.main:app --reload

cd ../frontend
npm install
npm run dev
```

This environment may not have Python or npm installed yet, so the scaffold is committed first and dependency setup can happen next.

## Suggested Roadmap

### Phase 0: Foundation

- Define the teacher persona
- Define the teaching skill format
- Define the student memory model
- Build a local web prototype

### Phase 1: First Real Teaching Loop

- Add a real LLM backend
- Add student login
- Save student learning memories
- Support one strong sample skill: junior math linear equations

### Phase 2: Teacher Skill Ecosystem

- Build a skill editor for teachers
- Add skill validation and preview
- Add review levels: official, verified teacher, community experiment

### Phase 3: School and Volunteer Deployment

- Add teacher dashboard
- Add class and student progress views
- Add self-hosting guide
- Add privacy and safety controls for minors

## License

License is not chosen yet. A public-good open-source license should be selected before accepting external contributions.
