from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="student")  # "admin" or "student"
    created_at = Column(DateTime, server_default=func.now())


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    degree = Column(String, nullable=False)
    branch = Column(String, nullable=False)
    semester = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    type = Column(String, nullable=False)  # Regular or Reappear
    file_path = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    year = Column(Integer, nullable=True)  # optional, auto-filled if not provided
    file_path = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, server_default=func.now())  


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, server_default=func.now())