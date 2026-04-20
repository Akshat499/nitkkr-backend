# create_admin.py
import sys
sys.path.append('.')

try:
    from db import SessionLocal
    from models import User
    from services.auth_service import hash_password

    db = SessionLocal()

    existing = db.query(User).filter(User.email == "admin@nitkkr.ac.in").first()
    if existing:
        print("⚠️ Admin already exists!")
        print(f"   Email: {existing.email}")
        print(f"   Role:  {existing.role}")
    else:
        admin = User(
            name="Admin",
            email="admin@nitkkr.ac.in",
            password_hash=hash_password("admin@123"),
            role="admin"
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print("✅ Admin created successfully!")
        print("📧 Email:    admin@nitkkr.ac.in")
        print("🔑 Password: admin@123")

    db.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()