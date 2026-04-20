from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from db import get_db
from models import Announcement
from services.dependencies import admin_only, get_current_user
from services.file_service import save_announcement_file
from services.result_extraction_service import index_announcement_pdf
from schemas import QueryRequest
import warnings
warnings.filterwarnings("ignore")

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.post("/upload")
async def upload_announcement(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(admin_only)
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    file_path = await save_announcement_file(file)

    announcement = Announcement(
        title=title, file_path=file_path,
        original_filename=file.filename
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    # Auto-index in vectorstore
    try:
        index_announcement_pdf(file_path, title, announcement.id)
        indexed = True
    except Exception as e:
        print(f"⚠️ Could not index announcement: {e}")
        indexed = False

    return {
        "message": "Announcement uploaded and indexed successfully",
        "id": announcement.id,
        "rag_indexed": indexed
    }


@router.get("/all")
def get_all_announcements(db: Session = Depends(get_db)):
    announcements = db.query(Announcement).order_by(Announcement.uploaded_at.desc()).all()
    return [
        {
            "id": a.id,
            "title": a.title,
            "original_filename": a.original_filename,
            "file_path": a.file_path,
            "uploaded_at": a.uploaded_at.isoformat() if a.uploaded_at else None,
        }
        for a in announcements
    ]


@router.post("/query")
async def query_announcement(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """RAG query over indexed announcements."""
    try:
        from services.result_extraction_service import get_announcement_vectorstore, get_llm
        from langchain.chains import RetrievalQA
        from langchain.prompts import PromptTemplate

        vs = get_announcement_vectorstore()
        retriever = vs.as_retriever(search_kwargs={"k": 5})

        PROMPT = PromptTemplate.from_template("""
You are a helpful NIT Kurukshetra assistant.
Answer the query based on official announcements.

Context:
{context}

Question: {question}

Answer:
""")
        qa_chain = RetrievalQA.from_chain_type(
            llm=get_llm(), chain_type="stuff", retriever=retriever,
            chain_type_kwargs={"prompt": PROMPT}
        )
        result = qa_chain.invoke({"query": request.question})
        return {"answer": result["result"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(admin_only)
):
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    import os
    if os.path.exists(announcement.file_path):
        os.remove(announcement.file_path)

    db.delete(announcement)
    db.commit()
    return {"message": "Announcement deleted successfully"}
