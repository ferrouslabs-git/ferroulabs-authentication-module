# Documentation Index

Last updated: 2026-03-23 — v3.0 (three-layer scope architecture)

---

## Quick Start

| Goal | Document |
|------|----------|
| **Integrate this module into a new project** | [setup_guide.md](setup_guide.md) |
| **AI agent / LLM context for coding** | [agent_reference.md](agent_reference.md) |
| **Cognito setup + SSO federation** | [cognito_and_sso_guide.md](cognito_and_sso_guide.md) |

---

## Document Catalog

### Core Documentation (v3.0)

| Document | Purpose | Audience |
|----------|---------|----------|
| [setup_guide.md](setup_guide.md) | Step-by-step host integration guide — DB wiring, middleware, routes, env vars, migrations, frontend | Developers |
| [agent_reference.md](agent_reference.md) | Complete system reference — file tree, data model, permission system, API endpoints, service signatures, invariants | AI agents, developers |

### Setup & Configuration

| Document | Purpose |
|----------|---------|
| [cognito_and_sso_guide.md](cognito_and_sso_guide.md) | Cognito base setup, SSO provider config (Google/Azure), federation wiring, multi-tenant SSO planning |

### Archive

| Folder | Contents |
|--------|----------|
| [old_docs/](old_docs/) | v1/v2 planning, implementation summaries, step docs, and priority reports — kept for historical reference |

---

## For AI Coding Agents

Start here: **[agent_reference.md](agent_reference.md)** — contains the complete system architecture, every file path, all function signatures, data model, permission system, API endpoints, and modification patterns.

Key files to read for full context:
1. `agent_reference.md` — system overview + reference
2. `backend/app/auth_usermanagement/auth_config.yaml` — role/permission definitions
3. `.github/copilot-instructions.md` — integration boundary rules

3. **After making changes:**
   - Update verification reports with completion status
   - Create/update implementation summaries
   - Update this index if adding new docs

4. **Before concluding session:**
   - Summarize work in implementation summary
   - Update completion checklists
   - Note blockers or next steps clearly

---

## 🛠️ Useful Commands

### Start Development Servers
```powershell
# Backend
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend
cd frontend
npm run dev
```

### Run Tests
```powershell
# Backend tests
cd backend
pytest tests/ -v

# Frontend build (validates compilation)
cd frontend
npm run build
```

### Access Admin Dashboard
- **URL:** http://localhost:5173/admin
- **Requires:** Admin or platform_admin role

---

## 📞 Quick Reference

**Project Root:** `c:\Users\ali_n\Documents\projects\ferrouslabs-auth-system\`

**Key Directories:**
- `/backend` - FastAPI application
- `/frontend` - React + Vite application
- `/documents` - This folder (planning & documentation)
- `/docs` - Code documentation (auth_rules.md)

**Database:** PostgreSQL (currently local, migration to RDS pending)

**Auth Provider:** AWS Cognito (eu-west-1)

**Email Service:** AWS SES (eu-west-1)
