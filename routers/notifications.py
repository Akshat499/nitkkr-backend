from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from db import get_db
from models import Notification
from services.dependencies import admin_only, get_current_user
from services.file_service import save_notification_file
from services.rag_service import index_notification, query_notifications
from schemas import QueryRequest
import warnings
warnings.filterwarnings("ignore")

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.post("/upload")
async def upload_notification(
    title: str = Form(...),
    year: int = Form(None),  # optional - if not provided, uses upload date year
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(admin_only)
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    file_path = await save_notification_file(file)

    notification = Notification(
        title=title,
        file_path=file_path,
        original_filename=file.filename
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    # Use provided year OR fallback to upload date year
    final_year = year if year else notification.uploaded_at.year

    # Update year in DB
    notification.year = final_year
    db.commit()

    # Index in vectorstore
    index_notification(file_path, title, final_year)

    return {
        "message": "Notice uploaded and indexed successfully",
        "id": notification.id,
        "year_indexed": final_year
    }


@router.get("/all")
def get_all_notifications(db: Session = Depends(get_db)):
    notifications = db.query(Notification).order_by(Notification.uploaded_at.desc()).all()
    return notifications


@router.post("/query")
async def query_notification(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        # Extract year from question automatically
        import re
        year_match = re.search(r'\b(20\d{2})\b', request.question)
        year = int(year_match.group(1)) if year_match else None

        answer = await query_notifications(request.question, year)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))