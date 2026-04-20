"""Fix admin role: update existing admin@nitkkr.ac.in role from 'student' to 'admin'"""
import sys
sys.path.append('.')

try:
    from db import SessionLocal
    from models import User
    from services.auth_service import hash_password

    db = SessionLocal()

    user = db.query(User).filter(User.email == "admin@nitkkr.ac.in").first()
    if user:
        print(f"Found user: {user.email}, current role: {user.role}")
        user.role = "admin"
        user.password_hash = hash_password("admin@123")  # Reset password to known value
        db.commit()
        db.refresh(user)
        print(f"✅ Role updated to: {user.role}")
        print("📧 Email:    admin@nitkkr.ac.in")
        print("🔑 Password: admin@123")
    else:
        # Create fresh admin
        admin = User(
            name="Admin",
            email="admin@nitkkr.ac.in",
            password_hash=hash_password("admin@123"),
            role="admin"
        )
        db.add(admin)
        db.commit()
        print("✅ Admin created fresh!")

    db.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
