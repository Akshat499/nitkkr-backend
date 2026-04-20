# NIT KKR Smart Edu Copilot — Integrated Project v2.0

## 🏗️ Architecture Overview

```
Frontend (HTML/JS)  ←→  Backend (FastAPI)  ←→  PostgreSQL + ChromaDB
     ↓                        ↓
   api.js              RAG Services
   auth.js             LLM (Groq/LLaMA 3.3)
```

## 📁 Project Structure

```
backend/
├── main.py                          # FastAPI app entry point
├── config.py                        # Config & env variables
├── db.py                            # SQLAlchemy setup
├── models.py                        # DB models (User, Result, Notification, Announcement)
├── schemas.py                       # Pydantic schemas
├── requirements.txt
├── .env                             # Environment variables
├── routers/
│   ├── auth.py                      # Login / Signup (JWT)
│   ├── admin.py                     # Result upload + stats (admin only)
│   ├── student.py                   # Chat, result extract, list results
│   ├── notifications.py             # Policy upload + RAG query
│   └── announcements.py             # Announcement upload + RAG query
├── services/
│   ├── auth_service.py              # JWT + password hashing
│   ├── dependencies.py              # Auth middleware
│   ├── file_service.py              # File save helpers
│   ├── llm_service.py               # SQL-based result file search
│   ├── rag_service.py               # RAG for notifications/policies
│   └── result_extraction_service.py # NEW: Result PDF extraction + unified chat
├── uploads/
│   ├── results/                     # Result PDFs
│   ├── notifications/               # Policy PDFs
│   └── announcements/               # Announcement PDFs
└── vectorstore*/                    # ChromaDB vector stores

frontend/
├── api.js                           # NEW: Unified backend API client
├── ask-ai-config.js                 # AI mode config
├── auth.js                          # Local auth (fallback)
├── main.js                          # Login form handler
├── dashboard-student.html           # Student dashboard (RAG chat + results)
├── dashboard-teacher.html           # Teacher dashboard (RAG chat)
├── dashboard-admin.html             # Admin dashboard (result upload + management)
└── ...
```

## 🚀 Setup

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env .env.local
# Edit .env with your values:
#   DATABASE_URL=postgresql://user:pass@localhost:5432/resultportal
#   JWT_SECRET=your_secret_key
#   GROQ_API_KEY=your_groq_api_key
#   JWT_EXPIRE_MINUTES=60

# Start server
uvicorn main:app --reload --port 8000
```

### Frontend

Simply open `index.html` in a browser, or serve with any HTTP server:
```bash
cd frontend
python -m http.server 3000
# Then open http://localhost:3000
```

## 🔌 Key API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth/login` | POST | ❌ | Login → JWT token |
| `/auth/signup` | POST | ❌ | Student signup |
| `/student/chat` | POST | ✅ | **Unified RAG chat** |
| `/student/chat/guest` | POST | ❌ | Guest RAG chat |
| `/student/extract-result` | POST | ✅ | **Extract marks from PDF** |
| `/student/results/list` | GET | ❌ | List available results |
| `/student/query` | POST | ✅ | NL result file search |
| `/admin/upload-result` | POST | 🔑Admin | Upload + auto-index result |
| `/admin/results` | GET | 🔑Admin | All uploaded results |
| `/admin/stats` | GET | 🔑Admin | Dashboard statistics |
| `/notifications/upload` | POST | 🔑Admin | Upload + index policy PDF |
| `/notifications/query` | POST | ✅ | RAG query on policies |
| `/announcements/upload` | POST | 🔑Admin | Upload + index announcement |
| `/announcements/query` | POST | ✅ | RAG query on announcements |

## 🧠 How the RAG Works

### Unified Chat (`/student/chat`)
The AI auto-detects query intent:
- **Result keywords** (marks, grade, sgpa, result, etc.) → searches result vectorstore
- **Policy keywords** (attendance, internship, scholarship, etc.) → searches notification vectorstore
- **Announcement keywords** → searches announcement vectorstore
- **General** → direct LLM response

### Result Extraction (`/student/extract-result`)
1. Student enters roll number or name
2. Backend iterates through all result PDFs in DB
3. LLM parses each PDF and extracts student-specific marks
4. Returns structured JSON: subjects, grades, SGPA, CGPA, status

## ✨ New Features Added

### Backend
- ✅ `result_extraction_service.py` — LLM-based marks extraction from PDFs
- ✅ Unified chat endpoint with auto intent detection
- ✅ Announcement RAG indexing
- ✅ Result PDF auto-indexing on upload
- ✅ Admin stats endpoint
- ✅ Guest chat endpoint (no auth required)
- ✅ Result delete endpoint

### Frontend
- ✅ `api.js` — unified backend API client
- ✅ Login with JWT backend (fallback to local auth)
- ✅ Student dashboard: **My Results** section with AI extraction
- ✅ Student AI chat → RAG backend (not direct Groq)
- ✅ Teacher AI chat → RAG backend (with Groq fallback)
- ✅ Admin: Result upload with auto-indexing
- ✅ Admin: Results management section
- ✅ Backend announcements shown in student dashboard
- ✅ Source badges in chat (Result DB / Policy Docs / Announcements / AI)
- ✅ Suggestion chips in student AI chat

## 🔧 Configuration

### Frontend — `api.js`
```javascript
const BASE_URL = 'http://localhost:8000';  // Change to your backend URL
```

### Backend — `.env`
```
DATABASE_URL=postgresql://postgres:password@localhost:5432/resultportal
JWT_SECRET=your_very_secret_key
JWT_EXPIRE_MINUTES=60
GROQ_API_KEY=your_groq_api_key
```

## 👤 Default Admin Account
Create via SQL or use the backend `/admin/create-admin` endpoint after logging in as admin.

```sql
INSERT INTO users (name, email, password_hash, role)
VALUES ('Admin', 'admin@nitkkr.ac.in', '<bcrypt_hash>', 'admin');
```
