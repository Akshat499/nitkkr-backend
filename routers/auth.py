from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_db
from models import User
from schemas import UserSignup, UserLogin, TokenResponse
from services.auth_service import hash_password, verify_password, create_access_token
from services.dependencies import get_current_user, admin_only

router = APIRouter(prefix="/auth", tags=["auth"])

# Roles that can only be created by an admin (not through public signup)
PRIVILEGED_ROLES = ["admin", "teacher"]


@router.post("/signup", response_model=TokenResponse)
def signup(user: UserSignup, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Public signup is only for students; teacher/admin must be created by admin
    allowed_role = "student" if user.role in PRIVILEGED_ROLES else user.role

    new_user = User(
        name=user.name,
        email=user.email,
        password_hash=hash_password(user.password),
        role=allowed_role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": str(new_user.id), "role": new_user.role, "name": new_user.name})
    return {"access_token": token, "token_type": "bearer", "role": new_user.role, "name": new_user.name}


@router.post("/login", response_model=TokenResponse)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(db_user.id), "role": db_user.role, "name": db_user.name})
    return {"access_token": token, "token_type": "bearer", "role": db_user.role, "name": db_user.name}


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current logged-in user info from token."""
    user_id = int(current_user.get("sub"))
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": db_user.id,
        "name": db_user.name,
        "email": db_user.email,
        "role": db_user.role,
        "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
    }


@router.post("/verify")
def verify_token(current_user: dict = Depends(get_current_user)):
    """Verify if current Bearer token is valid."""
    return {"valid": True, "role": current_user.get("role"), "name": current_user.get("name")}