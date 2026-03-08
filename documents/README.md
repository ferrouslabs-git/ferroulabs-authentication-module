# Documentation Index

Last updated: 2026-03-08

This folder contains all planning, verification, and implementation documentation for the ferrouslabs-auth-system project.

---

## 📋 Quick Start

**New to this project?** Start here:
1. Read [feature_details.md](feature_details.md) - System overview and capabilities
2. Review [current_stage_priority_todo.md](current_stage_priority_todo.md) - What to work on next

**Setting up Cognito?**
- See [cognito_setup.md](cognito_setup.md) - AWS Cognito configuration guide

**Working on Priority 2?**
- [priority2_verification_report.md](priority2_verification_report.md) - Gap analysis and completion status
- [priority2_manual_test_scenarios.md](priority2_manual_test_scenarios.md) - 40+ test scenarios
- [priority2_implementation_summary.md](priority2_implementation_summary.md) - Tonight's work summary

---

## 📁 Document Catalog

### System Overview
| Document | Purpose | Audience |
|----------|---------|----------|
| [feature_details.md](feature_details.md) | System identity, intent, and feature inventory | AI agents, developers |

### Planning & Priorities
| Document | Purpose | Audience |
|----------|---------|----------|
| [current_stage_priority_todo.md](current_stage_priority_todo.md) | Recommended priority order with checklists | Team leads, developers |

### Setup Guides
| Document | Purpose | Audience |
|----------|---------|----------|
| [cognito_setup.md](cognito_setup.md) | AWS Cognito configuration steps | DevOps, developers |

### Priority 2 (Admin UI)
| Document | Purpose | Audience |
|----------|---------|----------|
| [priority2_verification_report.md](priority2_verification_report.md) | Technical verification and gap analysis | Developers, QA |
| [priority2_manual_test_scenarios.md](priority2_manual_test_scenarios.md) | Detailed test scenarios (40+) | QA, developers |
| [priority2_implementation_summary.md](priority2_implementation_summary.md) | Implementation summary for tonight | Team leads, developers |

### Archive
| Document | Purpose | Status |
|----------|---------|--------|
| [old_docs/](old_docs/) | Earlier planning documents | Reference only |

---

## 🎯 Current Project Status

**Priority 2 (Admin UI):** 🟡 85% Complete
- ✅ Implementation done
- ⏳ Manual testing pending
- See [priority2_implementation_summary.md](priority2_implementation_summary.md)

**Priority 1 (RDS Migration):** ⏳ Scheduled for tomorrow
- See [current_stage_priority_todo.md](current_stage_priority_todo.md)

**Priority 3 (Mock App):** ⏳ Not started

---

## 🔄 Document Maintenance

### When to Update This Index
- When adding new top-level documents
- When changing priority order
- When completing major milestones
- At end of each work session

### Document Naming Convention
- System overview: `feature_details.md`, `architecture.md`
- Planning: `priority_todo.md`, `roadmap.md`
- Setup: `[service]_setup.md` (e.g., `cognito_setup.md`)
- Verification: `[priority]_verification_report.md`
- Testing: `[priority]_manual_test_scenarios.md`
- Implementation: `[priority]_implementation_summary.md`

---

## 📝 For AI Coding Agents

When starting a new session:

1. **Context gathering:**
   - Read [feature_details.md](feature_details.md) for system overview
   - Read [current_stage_priority_todo.md](current_stage_priority_todo.md) for current priorities

2. **Before making changes:**
   - Check relevant verification reports
   - Review test scenarios
   - Note any schema change warnings

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
