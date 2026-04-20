import warnings
warnings.filterwarnings("ignore")
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_core.documents import Document
from config import GROQ_API_KEY
from datetime import datetime
import re

VECTORSTORE_DIR = "vectorstore"
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

def get_vectorstore():
    return Chroma(
        persist_directory=VECTORSTORE_DIR,
        embedding_function=get_embeddings()
    )

def index_notification(file_path: str, title: str, year: int):
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    chunks = text_splitter.split_documents(documents)

    for chunk in chunks:
        chunk.metadata["title"] = title
        chunk.metadata["year"] = year
        chunk.metadata["file_path"] = file_path
        chunk.metadata["uploaded_at"] = datetime.now().strftime("%Y-%m-%d")
        chunk.metadata["source_label"] = f"{title} ({year})"

    vectorstore = get_vectorstore()
    vectorstore.add_documents(chunks)
    print(f"✅ Indexed {len(chunks)} chunks for: {title} (year: {year})")


async def query_notifications(question: str, year: int = None):
    vectorstore = get_vectorstore()

    # Get all available years from vectorstore
    all_docs = vectorstore.get()
    available_years = []
    if all_docs and all_docs['metadatas']:
        available_years = sorted(set(
            m.get('year') for m in all_docs['metadatas'] if m.get('year')
        ))

    latest_year = max(available_years) if available_years else None
    oldest_year = min(available_years) if available_years else None

    # Smart year detection from question
    question_lower = question.lower()
    year_match = re.search(r'\b(20\d{2})\b', question_lower)
    latest_keywords = ["latest", "current", "recent", "new", "updated", "now", "today"]
    old_keywords = ["old", "previous", "earlier", "past", "before", "last year", "outdated"]
    compare_keywords = ["compare", "difference", "changed", "vs", "versus", "differ", "change"]

    if any(k in question_lower for k in compare_keywords):
        filter_year = None
    elif year_match:
        filter_year = int(year_match.group(1))
    elif any(k in question_lower for k in latest_keywords):
        filter_year = latest_year
    elif any(k in question_lower for k in old_keywords):
        filter_year = oldest_year
    else:
        filter_year = None

    print(f"Question: {question}")
    print(f"Year filter: {filter_year} | Available years: {available_years}")

    # Retrieve relevant documents
    if filter_year:
        retriever = vectorstore.as_retriever(
            search_kwargs={"k": 5, "filter": {"year": filter_year}}
        )
    else:
        retriever = vectorstore.as_retriever(search_kwargs={"k": 8})

    docs = retriever.invoke(question)
    context = "\n\n".join([doc.page_content for doc in docs])

    # Build prompt manually — no RetrievalQA needed
    prompt = f"""You are a helpful university assistant for NIT Kurukshetra.
Available policy years in database: {available_years}
Latest policy year: {latest_year}

Answer the student's question based on the provided policy documents.

Important guidelines:
- Always mention which year's policy you are referring to
- If question asks "latest" or "current", answer ONLY from year {latest_year}
- If question mentions a specific year like "2022", answer ONLY from that year
- If question asks to compare, clearly show differences year by year
- Format your answer clearly with bullet points
- If information is not found in documents, say "This information is not available in current policies"

Context:
{context}

Question: {question}

Answer:"""

    llm = get_llm()
    response = llm.invoke(prompt)
    return response.content