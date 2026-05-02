# Architecture

OpenTeacher is designed as a modular AI teacher system.

## Current Stack Decision

- Python backend
- React web frontend
- PostgreSQL relational database
- Memory storage to be decided later
- RAG storage to be decided later

The memory and RAG storage choices should stay behind interfaces so the project can evolve without rewriting the agent harness.

## Backend Modules

```text
app/
  api/          HTTP routes
  core/         settings and shared infrastructure
  db/           relational database setup
  models/       SQLAlchemy models
  schemas/      API request and response schemas
  services/     agent, memory, skill, and RAG interfaces
```

## First Runtime Flow

1. Student sends a message from the React app.
2. Backend receives the message through `/api/v1/teacher/chat`.
3. Agent harness loads student context, skill context, and teaching policy.
4. Teacher service generates a guided response.
5. Memory service records a lightweight learning event.
6. Frontend displays the teacher response.

## Storage Boundary

PostgreSQL is the source of truth for relational product data:

- students
- classes
- teachers and volunteers
- conversations
- messages
- skill metadata
- learning events

Memory and RAG may later use:

- PostgreSQL tables first
- pgvector
- a vector database
- object storage plus search index
- hybrid storage

The first implementation should expose service interfaces before choosing the final storage.
