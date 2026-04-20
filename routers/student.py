from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from db import get_db
from models import Result
from schemas import QueryRequest, UnifiedChatRequest
from services.dependencies import get_current_user
from services.llm_service import query_results
from services.result_extraction_service import (
    extract_student_result, query_result_rag, unified_chat
)
import os, re

router = APIRouter(prefix="/student", tags=["student"])


async def _do_extract(request, roll_number, student_name, result_id, branch, semester, db):
    """Core extraction logic shared by auth + guest endpoints."""
    if not roll_number and not student_name:
        roll_pattern = re.search(r'\b(\d{2}[A-Za-z]{2,5}\d{3,6})\b', request.question or "")
        if roll_pattern:
            roll_number = roll_pattern.group(1).upper()

    if not roll_number and not student_name:
        raise HTTPException(status_code=400, detail="Please provide roll number or student name.")

    query_obj = db.query(Result)
    if result_id: query_obj = query_obj.filter(Result.id == result_id)
    if branch: query_obj = query_obj.filter(Result.branch == branch)
    if semester: query_obj = query_obj.filter(Result.semester == semester)
    targets = query_obj.order_by(Result.uploaded_at.desc()).all()

    if not targets:
        return {"found": False, "message": "No result PDFs uploaded yet. Please contact your admin."}

    for result_file in targets:
        if not os.path.exists(result_file.file_path):
            continue
        try:
            data = await extract_student_result(
                result_file.file_path,
                roll_number=roll_number,
                student_name=student_name
            )
            if data.get("found"):
                data["result_metadata"] = {
                    "degree": result_file.degree,
                    "branch": result_file.branch,
                    "semester": result_file.semester,
                    "year": result_file.year,
                    "type": result_file.type,
                    "filename": result_file.original_filename,
                    "file_path": result_file.file_path,
                }
                return data
        except Exception as e:
            print(f"Error extracting from {result_file.original_filename}: {e}")
            continue

    search_label = f"Roll: {roll_number}" if roll_number else f"Name: {student_name}"
    filter_label = (f" | Branch: {branch}" if branch else "") + (f" | Sem: {semester}" if semester else "")
    return {
        "found": False,
        "message": f"Result not found for {search_label}{filter_label}. Check your roll number or try removing filters."
    }


@router.post("/extract-result/guest")
async def extract_result_guest(
    request: QueryRequest,
    roll_number: str = Query(None),
    student_name: str = Query(None),
    result_id: int = Query(None),
    branch: str = Query(None),
    semester: int = Query(None),
    db: Session = Depends(get_db)
):
    """Guest result extraction — NO login required."""
    try:
        return await _do_extract(request, roll_number, student_name, result_id, branch, semester, db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-result")
async def extract_result(
    request: QueryRequest,
    roll_number: str = Query(None),
    student_name: str = Query(None),
    result_id: int = Query(None),
    branch: str = Query(None),
    semester: int = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Auth-required result extraction."""
    try:
        return await _do_extract(request, roll_number, student_name, result_id, branch, semester, db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query(
    request: QueryRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        results = await query_results(request.question)
        return {"results": results} if results else {"results": [], "message": "No results found."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def unified_chat_endpoint(
    request: UnifiedChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        response = await unified_chat(request.question, user_id=current_user.get("sub"))
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/guest")
async def guest_chat_endpoint(request: UnifiedChatRequest):
    try:
        return await unified_chat(request.question, user_id=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/list")
def list_results(
    degree: str = Query(None),
    branch: str = Query(None),
    semester: int = Query(None),
    year: int = Query(None),
    result_type: str = Query(None),
    db: Session = Depends(get_db)
):
    """List all available results — no auth required."""
    q = db.query(Result)
    if degree: q = q.filter(Result.degree == degree)
    if branch: q = q.filter(Result.branch == branch)
    if semester: q = q.filter(Result.semester == semester)
    if year: q = q.filter(Result.year == year)
    if result_type: q = q.filter(Result.type == result_type)
    return [
        {"id": r.id, "degree": r.degree, "branch": r.branch, "semester": r.semester,
         "year": r.year, "type": r.type, "original_filename": r.original_filename,
         "file_path": r.file_path,
         "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None}
        for r in q.order_by(Result.uploaded_at.desc()).all()
    ]