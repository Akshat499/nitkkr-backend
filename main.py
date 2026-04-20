from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from db import engine, Base
import models
from routers import auth, admin, student, notifications, announcements

app = FastAPI(title="NIT KKR Smart Edu Copilot", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

# Include all routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(student.router)
app.include_router(notifications.router)
app.include_router(announcements.router)

# Serve uploaded files statically
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
def read_root():
    return {
        "message": "NIT KKR Smart Edu Copilot API v2.0",
        "endpoints": {
            "auth": ["/auth/signup", "/auth/login", "/auth/me", "/auth/verify"],
            "student": [
                "/student/chat", "/student/chat/guest",
                "/student/extract-result", "/student/extract-result/guest",
                "/student/results/list", "/student/query"
            ],
            "admin": [
                "/admin/upload-result", "/admin/results", "/admin/stats",
                "/admin/create-admin", "/admin/create-teacher",
                "/admin/users", "/admin/options"
            ],
            "notifications": ["/notifications/upload", "/notifications/all", "/notifications/query"],
            "announcements": ["/announcements/upload", "/announcements/all", "/announcements/query"],
        }
    }

@app.get("/health")
def health():
    return {"status": "ok"}