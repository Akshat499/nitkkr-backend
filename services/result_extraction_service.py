"""
Result Extraction Service
- Parses result PDFs using hybrid deterministic+LLM approach
- NIT KKR result PDFs show only SGPA per student (not per-subject marks)
- Indexes result content in ChromaDB for RAG queries
- Supports natural language queries like "mera result kya hai semester 3 mein"
"""
import warnings
warnings.filterwarnings("ignore")
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from config import GROQ_API_KEY
from datetime import datetime
import re, json

RESULT_VECTORSTORE_DIR = "vectorstore_results"
ANNOUNCEMENT_VECTORSTORE_DIR = "vectorstore_announcements"

_embeddings = None
_llm = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = FastEmbedEmbeddings()
    return _embeddings

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.3-70b-versatile")
    return _llm

def get_result_vectorstore():
    return Chroma(
        persist_directory=RESULT_VECTORSTORE_DIR,
        embedding_function=get_embeddings()
    )

def get_announcement_vectorstore():
    return Chroma(
        persist_directory=ANNOUNCEMENT_VECTORSTORE_DIR,
        embedding_function=get_embeddings()
    )

def index_result_pdf(file_path: str, degree: str, branch: str, semester: int, year: int, result_type: str, result_id: int):
    """Index result PDF content in vectorstore for RAG queries."""
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )
    chunks = text_splitter.split_documents(documents)

    for chunk in chunks:
        chunk.metadata.update({
            "type": "result",
            "degree": degree,
            "branch": branch,
            "semester": semester,
            "year": year,
            "result_type": result_type,
            "result_id": result_id,
            "indexed_at": datetime.now().strftime("%Y-%m-%d"),
            "source_label": f"{degree} {branch} Sem {semester} {result_type} {year}"
        })

    vs = get_result_vectorstore()
    vs.add_documents(chunks)
    print(f"✅ Indexed {len(chunks)} chunks for result: {degree} {branch} Sem {semester} {year} ({result_type})")

def index_announcement_pdf(file_path: str, title: str, ann_id: int):
    """Index announcement PDF content in vectorstore."""
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=80
    )
    chunks = text_splitter.split_documents(documents)

    for chunk in chunks:
        chunk.metadata.update({
            "type": "announcement",
            "title": title,
            "ann_id": ann_id,
            "indexed_at": datetime.now().strftime("%Y-%m-%d"),
        })

    vs = get_announcement_vectorstore()
    vs.add_documents(chunks)
    print(f"✅ Indexed announcement: {title}")


# ─────────────────────────────────────────────────────────────
# NIT KKR Subject Code → Name Map
# ─────────────────────────────────────────────────────────────
SUBJECT_NAME_MAP = {
    # Sem 3 CSE
    "MAIC-201": "Discrete Mathematics",
    "MARC-201": "Discrete Mathematics",
    "CSPC-201": "Computer Programming",
    "CSPC-203": "Data Structures",
    "CSPC-205": "Object-Oriented Programming",
    "CSPC-207": "Software Engineering",
    "CSPC-209": "IoT Programming",
    # Sem 1 CSE/ECE/IIoT
    "CSPC-101": "Introduction to Computing",
    "CSPC-103": "Programming Fundamentals",
    "CSPC-105": "Digital Logic Design",
    "MATH-101": "Mathematics I",
    "PHYS-101": "Engineering Physics",
    "CHEM-101": "Engineering Chemistry",
    # Sem 4 Re-appear
    "CSPC-401": "Theory of Computation",
    "CSPC-403": "Computer Organisation",
    "CSPC-405": "Operating Systems",
    "CSPC-407": "DBMS",
    "CSPC-409": "Computer Networks",
    # ECE
    "ECPC-201": "Electronic Devices & Circuits",
    "ECPC-203": "Signals & Systems",
    "ECPC-205": "Digital Electronics",
}


def _parse_sgpa_value(raw: str) -> str:
    """Convert '8 2000' or '8.2000' to '8.2000'."""
    raw = raw.strip()
    # Handle "8 2000" (space instead of decimal point — OCR artifact)
    m = re.match(r'^(\d{1,2})\s+(\d{4})$', raw)
    if m:
        return f"{m.group(1)}.{m.group(2)}"
    # Handle "8.2000" directly
    m2 = re.match(r'^(\d{1,2}\.\d{1,4})$', raw)
    if m2:
        try:
            val = float(m2.group(1))
            return f"{val:.4f}"
        except:
            pass
    return raw


def _deterministic_extract_page(page_text: str, search_term: str):
    """
    Parse a single PDF page to find a student's SGPA and reappear info.
    
    NIT KKR PDFs use multi-column layout. PyPDF extracts column-by-column, so:
    - Column 1: Sr.No + Roll No rows (like "17 124102014 Sanj")
    - Column 2: Full names
    - Column 3: Father names / Re. entries
    - Column 4: SGPA values (one per student, in same order as Sr.No column)
    
    Algorithm:
    1. Find all (sr_no, roll_no) pairs on this page → ordered student list
    2. Find all SGPA-like values on this page → ordered SGPA list
    3. Match by index: student[i] → sgpa[i]
    4. Find Re. entries for this specific student
    """
    lines = page_text.split('\n')
    search_lower = search_term.lower()
    
    # ── Step 1: Extract all student rows (Sr.No + Roll) ──────────────
    # Pattern: "17 124102014" or "17 124102014 Sanj" at start of line
    student_rows = []  # list of (line_idx, sr_no, roll_no)
    for idx, line in enumerate(lines):
        m = re.match(r'^\s*(\d{1,3})\s+(\d{9,12})', line.strip())
        if m:
            sr_no = int(m.group(1))
            roll_no = m.group(2)
            student_rows.append((idx, sr_no, roll_no))
    
    # ── Step 2: Find target student ──────────────────────────────────
    target_row = None
    target_pos = None  # index in student_rows list
    for i, (idx, sr_no, roll_no) in enumerate(student_rows):
        if search_lower in roll_no.lower():
            target_row = (idx, sr_no, roll_no)
            target_pos = i
            break
    
    if target_row is None:
        return None
    
    target_line_idx, target_sr_no, found_roll = target_row
    
    # ── Step 3: Extract all SGPA-like values from the page ───────────
    # SGPA patterns: "8.2000", "8 2000", "10 0000", "I 4000" (I=Incomplete), "R,..." (result late)
    sgpa_values = []  # list of (line_idx, raw_value, normalized)
    re_entries = []   # list of (line_idx, subject_code, raw_line)
    
    sgpa_re = re.compile(r'^\s*(\d{1,2}[\s.]\d{4})\s*$')
    ten_re = re.compile(r'^\s*(10[\s.]\d{4})\s*$')
    incomplete_re = re.compile(r'^\s*I[\s.]\d{4}\s*$')
    reappear_re = re.compile(r'Re\.?\s+([A-Z]{2,6}-\d{3}[A-Z]?)', re.IGNORECASE)
    
    for idx, line in enumerate(lines):
        ls = line.strip()
        # SGPA value line
        if sgpa_re.match(ls) or ten_re.match(ls):
            m = re.match(r'(\d{1,2})[\s.](\d{4})', ls)
            if m:
                normalized = f"{m.group(1)}.{m.group(2)}"
                try:
                    val = float(normalized)
                    if 0.5 <= val <= 10.0:
                        sgpa_values.append((idx, ls, normalized))
                except:
                    pass
        elif '.' in ls:
            # Handle "8.2000" format
            m = re.match(r'^(\d{1,2}\.\d{4})$', ls)
            if m:
                try:
                    val = float(m.group(1))
                    if 0.5 <= val <= 10.0:
                        sgpa_values.append((idx, ls, f"{val:.4f}"))
                except:
                    pass
        # Incomplete / special
        elif incomplete_re.match(ls):
            sgpa_values.append((idx, ls, "Incomplete"))
        # Re. entry
        m_re = reappear_re.search(ls)
        if m_re:
            re_entries.append((idx, m_re.group(1), ls))
    
    # ── Step 4: Match SGPA by position ──────────────────────────────
    # target_pos is 0-indexed position in student_rows on this page
    found_sgpa = None
    if 0 <= target_pos < len(sgpa_values):
        sgpa_raw = sgpa_values[target_pos][2]
        if sgpa_raw != "Incomplete":
            found_sgpa = sgpa_raw

    # ── Step 5: Find Re. entries for this student ────────────────────
    # Re. entries appear between consecutive SGPA values.
    # Student at target_pos: SGPA at sgpa_values[target_pos-1] (line idx) < Re. line < sgpa_values[target_pos] (line idx)
    reappear_codes = []
    if re_entries:
        # Get the SGPA line index boundaries for this student's slot
        prev_sgpa_idx = sgpa_values[target_pos - 1][0] if target_pos > 0 else -1
        curr_sgpa_idx = sgpa_values[target_pos][0] if target_pos < len(sgpa_values) else 99999
        
        for re_line_idx, re_code, re_raw in re_entries:
            if prev_sgpa_idx < re_line_idx < curr_sgpa_idx:
                reappear_codes.append(re_code)
    
    # ── Step 6: Find student full name ──────────────────────────────
    found_name = None
    window_start = max(0, target_line_idx - 20)
    window_end = min(len(lines), target_line_idx + 30)
    window_text = "\n".join(lines[window_start:window_end])
    
    name_candidates = re.findall(r'\b([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){1,3})\b', window_text)
    SKIP_KW = {"Discrete", "Computer", "Software", "Object", "Data", "National", "Institute",
               "Notification", "Subjects"}
    student_names = [n for n in name_candidates
                     if 2 <= len(n.split()) <= 4
                     and not any(kw in n for kw in SKIP_KW)]
    if student_names:
        roll_rel = target_line_idx - window_start
        window_lines = lines[window_start:window_end]
        best_name = None
        best_dist = 9999
        for sn in student_names:
            for li, ln in enumerate(window_lines):
                if sn in ln:
                    dist = abs(li - roll_rel)
                    if dist < best_dist:
                        best_dist = dist
                        best_name = sn
        found_name = best_name
    
    return {
        "found_roll": found_roll,
        "found_student_name": found_name,
        "found_sgpa": found_sgpa,
        "reappear_codes": reappear_codes,
    }


def _deterministic_extract(documents: list, search_term: str, is_roll: bool):
    """
    Iterate over PDF pages and use page-level extraction to find the student.
    Returns the first successful result, or None if not found.
    """
    search_lower = search_term.lower()
    for doc in documents:
        result = _deterministic_extract_page(doc.page_content, search_lower)
        if result is not None:
            return result
    return None


# ─────────────────────────────────────────────────────────────
# Main extraction function
# ─────────────────────────────────────────────────────────────
async def extract_student_result(file_path: str, roll_number: str = None, student_name: str = None) -> dict:
    """
    Hybrid extraction:
    1. Deterministic parser for NIT KKR SGPA-only PDFs (most result PDFs).
    2. LLM fallback for PDFs that contain actual per-subject marks tables.
    """
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    if not roll_number and not student_name:
        return {"error": "Please provide roll number or student name"}

    search_term = roll_number if roll_number else student_name
    identifier_type = "Roll Number" if roll_number else "Student Name"
    search_lower = search_term.lower()
    is_roll = bool(roll_number)

    # Combine all page text
    full_text = "\n".join([doc.page_content for doc in documents])

    # ── STEP 1: Extract subject codes from header (page 1 usually) ──
    all_subject_codes = re.findall(r'\b([A-Z]{2,6}-\d{3}[A-Z]?)\b', full_text)
    # Dedupe while preserving order, ignore repeat occurrences from student rows
    seen = set()
    header_subjects = []
    for sc in all_subject_codes:
        if sc not in seen:
            seen.add(sc)
            header_subjects.append(sc)
    # Keep only the first N unique codes (header), subsequent ones come from Re. entries
    # Heuristic: take the first ≤8 unique codes as the semester subjects
    semester_subjects = header_subjects[:8] if len(header_subjects) > 8 else header_subjects

    # ── STEP 2: Try deterministic extraction ────────────────────────
    parsed = _deterministic_extract(documents, search_lower, is_roll)

    if parsed:
        found_roll = parsed["found_roll"] or search_term
        found_name = parsed["found_student_name"] or search_term
        found_sgpa = parsed["found_sgpa"]
        reappear_codes = parsed["reappear_codes"]

        # Build subjects list — only show subjects if there are reappear entries
        subjects_list = []
        if reappear_codes:
            for sc in semester_subjects:
                sname = SUBJECT_NAME_MAP.get(sc, sc)
                is_re = sc in reappear_codes
                subjects_list.append({
                    "subject_code": sc,
                    "subject_name": sname,
                    "marks_obtained": "N/A",
                    "max_marks": "N/A",
                    "grade": "Re" if is_re else "Pass"
                })

        result_status = "Reappear" if reappear_codes else "Pass"
        remarks = None
        if reappear_codes:
            remarks = f"Reappear in: {', '.join(reappear_codes)}"
        else:
            remarks = "Individual subject marks not available in this PDF — only overall SGPA is declared."

        return {
            "found": True,
            "student_name": found_name,
            "roll_number": found_roll,
            "subjects": subjects_list,
            "total_marks": None,
            "percentage": None,
            "result_status": result_status,
            "sgpa": found_sgpa,
            "cgpa": None,
            "remarks": remarks,
        }

    # ── STEP 3: Deterministic failed — try LLM fallback ─────────────
    relevant_pages = []
    for i, doc in enumerate(documents):
        if search_lower in doc.page_content.lower():
            start = max(0, i - 1)
            end = min(len(documents), i + 2)
            for j in range(start, end):
                if j not in [p[0] for p in relevant_pages]:
                    relevant_pages.append((j, documents[j].page_content))

    if not relevant_pages:
        name_parts = search_lower.split()
        for i, doc in enumerate(documents):
            if any(part in doc.page_content.lower() for part in name_parts if len(part) > 3):
                start = max(0, i - 1)
                end = min(len(documents), i + 2)
                for j in range(start, end):
                    if j not in [p[0] for p in relevant_pages]:
                        relevant_pages.append((j, documents[j].page_content))
            if len(relevant_pages) >= 6:
                break

    if not relevant_pages:
        return {
            "found": False,
            "message": f"Student with {identifier_type} '{search_term}' not found in this result."
        }

    relevant_pages.sort(key=lambda x: x[0])
    context_text = "\n\n--- PAGE BREAK ---\n\n".join([p[1] for p in relevant_pages])
    if len(context_text) > 12000:
        context_text = context_text[:12000]

    llm = get_llm()
    prompt = f"""You are a university result extraction assistant for NIT Kurukshetra.

Find and extract the result for the student with {identifier_type}: {search_term}

CRITICAL NOTE: This PDF shows SGPA per student, NOT individual subject marks.
The column after student names contains SGPA (e.g., 8.2000, 9.5000) — NOT marks.
Do NOT put SGPA values into the marks_obtained field.

Result PDF Content:
{context_text}

Return a JSON object:
{{
  "found": true,
  "student_name": "full name",
  "roll_number": "roll number",
  "subjects": [],
  "total_marks": null,
  "percentage": null,
  "result_status": "Pass or Reappear",
  "sgpa": "SGPA value like 8.2000",
  "cgpa": null,
  "remarks": "Reappear in: SUBJECTCODE if reappear, else null"
}}

If student not found: {{"found": false, "message": "Not found"}}
Return ONLY valid JSON, no markdown.
"""

    response = llm.invoke(prompt)
    raw = response.content.strip()
    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return {"found": False, "message": f"Could not parse result. Raw: {raw[:200]}"}


async def query_result_rag(question: str, degree: str = None, branch: str = None, semester: int = None, year: int = None) -> str:
    """RAG query over indexed result PDFs."""
    vs = get_result_vectorstore()

    # Build filter
    filter_dict = {}
    if branch: filter_dict["branch"] = branch
    if semester: filter_dict["semester"] = semester
    if year: filter_dict["year"] = year
    if degree: filter_dict["degree"] = degree

    if filter_dict:
        retriever = vs.as_retriever(search_kwargs={"k": 6, "filter": filter_dict})
    else:
        retriever = vs.as_retriever(search_kwargs={"k": 8})

    from langchain.chains import RetrievalQA

    PROMPT = PromptTemplate.from_template("""
You are a helpful NIT Kurukshetra result assistant.
Answer the student's query about exam results based on the provided result documents.

Guidelines:
- Find the specific student's marks if roll number or name is mentioned
- Present marks in a clear, easy-to-read table format
- Mention subject names, marks obtained, max marks, and grades
- If SGPA/CGPA is available, mention it
- Be friendly and encouraging
- If a student is not found, suggest they check their roll number or contact the exam section

Context from result documents:
{context}

Student's Question: {question}

Answer (be helpful and clear):
""")

    qa_chain = RetrievalQA.from_chain_type(
        llm=get_llm(),
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": PROMPT}
    )

    result = qa_chain.invoke({"query": question})
    return result["result"]

async def unified_chat(question: str, user_id: str = None) -> dict:
    """
    Unified chat endpoint — auto-detects intent and routes to appropriate service:
    - Result queries → result vectorstore
    - Policy/notification queries → notification vectorstore  
    - Announcement queries → announcement vectorstore
    - General queries → LLM direct
    Returns: {answer, source_type, sources}
    """
    q_lower = question.lower()

    # Detect intent
    result_keywords = ["result", "marks", "grade", "sgpa", "cgpa", "pass", "fail", "semester result",
                       "score", "subject marks", "mera result", "my result", "percentage", "reappear"]
    notification_keywords = ["policy", "attendance", "internship", "scholarship", "rule", "regulation",
                              "notice", "circular", "guideline", "leave", "exam policy", "fee"]
    announcement_keywords = ["announcement", "notice", "holi", "holiday", "admission", "merit", "scholarship list"]

    is_result = any(k in q_lower for k in result_keywords)
    is_notification = any(k in q_lower for k in notification_keywords)
    is_announcement = any(k in q_lower for k in announcement_keywords)

    sources = []

    if is_result:
        try:
            answer = await query_result_rag(question)
            return {"answer": answer, "source_type": "result", "sources": ["Result Database"]}
        except Exception as e:
            print(f"[unified_chat] result branch error: {e}")

    if is_notification:
        try:
            from services.rag_service import query_notifications
            answer = await query_notifications(question)
            return {"answer": answer, "source_type": "notification", "sources": ["Policy Documents"]}
        except Exception as e:
            print(f"[unified_chat] notification branch error: {e}")

    if is_announcement:
        try:
            vs = get_announcement_vectorstore()
            retriever = vs.as_retriever(search_kwargs={"k": 5})
            from langchain.chains import RetrievalQA
            PROMPT = PromptTemplate.from_template("""
You are a helpful NIT Kurukshetra assistant.
Answer the student's query based on official announcements.

Context:
{context}

Question: {question}

Answer:
""")
            qa_chain = RetrievalQA.from_chain_type(
                llm=get_llm(), chain_type="stuff", retriever=retriever,
                chain_type_kwargs={"prompt": PROMPT}
            )
            result = qa_chain.invoke({"query": question})
            return {"answer": result["result"], "source_type": "announcement", "sources": ["Announcements"]}
        except Exception as e:
            print(f"[unified_chat] announcement branch error: {e}")

    # Fallback: general LLM response with NIT KKR context
    try:
        llm = get_llm()
        fallback_prompt = f"""You are a helpful AI assistant for NIT Kurukshetra students and faculty.
Answer the following question in a friendly, helpful way.
If you don't have specific information about NIT KKR, provide general helpful information.

Question: {question}

Answer:"""
        response = llm.invoke(fallback_prompt)
        return {
            "answer": response.content,
            "source_type": "general",
            "sources": ["AI Assistant"]
        }
    except Exception as e:
        print(f"[unified_chat] fallback LLM error: {e}")
        # Check for common API key issues
        err_str = str(e).lower()
        if "api_key" in err_str or "expired" in err_str or "invalid" in err_str or "unauthorized" in err_str or "401" in err_str:
            return {
                "answer": "⚠️ The AI service is currently unavailable because the API key has expired or is invalid. Please contact the administrator to renew the Groq API key.",
                "source_type": "error",
                "sources": []
            }
        return {
            "answer": "I'm sorry, I encountered an error while processing your question. Please try again later or contact the administrator.",
            "source_type": "error",
            "sources": []
        }