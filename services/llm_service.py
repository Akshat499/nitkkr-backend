from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from config import GROQ_API_KEY, DATABASE_URL
from sqlalchemy import create_engine, text
import re

# SQLAlchemy engine — no langchain.chains needed
engine = create_engine(DATABASE_URL)

llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.3-70b-versatile"
)

PROMPT_TEMPLATE = """You are a SQL expert. Convert the user's question to a PostgreSQL SELECT query.

Table: results
Columns: id, degree, branch, semester, year, type, file_path, original_filename, uploaded_at

THE DATABASE STORES EXACT VALUES - YOU MUST USE THESE EXACT VALUES IN WHERE CLAUSE:
- degree column stores: 'BTech', 'MTech', 'BCA', 'MCA'
- branch column stores: 'CSE', 'ECE', 'ME', 'CE', 'IT', 'Electrical', 'IOT'
- type column stores: 'Regular', 'Reappear'

USER INPUT MAPPINGS - convert user input to exact database values:
Degree: "btech"/"b.tech"/"be" → use 'BTech' in WHERE clause
Branch: "cse"/"cs"/"computer science"/"computer" → use 'CSE' in WHERE clause
Branch: "ece"/"electronics" → use 'ECE' in WHERE clause
Branch: "me"/"mechanical" → use 'ME' in WHERE clause
Branch: "ce"/"civil" → use 'CE' in WHERE clause
Branch: "it"/"information technology" → use 'IT' in WHERE clause
Branch: "electrical"/"ee" → use 'Electrical' in WHERE clause
Branch: "iot"/"internet of things" → use 'IOT' in WHERE clause
Type: "regular"/"main" → use 'Regular' in WHERE clause
Type: "reappear"/"back"/"backlog"/"ex" → use 'Reappear' in WHERE clause

Rules:
- ONLY generate SELECT queries
- Use EXACT values in WHERE clause, never lowercase
- SELECT: id, degree, branch, semester, year, type, original_filename, file_path
- Limit to 10 results max
- Return ONLY the raw SQL query, no explanation, no markdown

Question: {question}
SQL Query:"""


def extract_sql(raw: str) -> str:
    match = re.search(r'```sql\s*(.*?)\s*```', raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r'(SELECT\s+.*?;)', raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r'(SELECT\s+.*?)(?:\n\n|$)', raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return raw.strip()


async def query_results(question: str):
    prompt = PROMPT_TEMPLATE.format(question=question)
    response = llm.invoke(prompt)
    raw = response.content.strip()

    sql = extract_sql(raw)

    print("=== Generated SQL ===")
    print(sql)
    print("====================")

    if not sql.upper().startswith("SELECT"):
        raise Exception(f"Could not extract valid SQL. Got: {sql[:100]}")

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchall()

    print("=== Rows found:", len(rows), "===")

    output = []
    for row in rows:
        output.append({
            "id": row[0],
            "degree": row[1],
            "branch": row[2],
            "semester": row[3],
            "year": row[4],
            "type": row[5],
            "original_filename": row[6],
            "file_path": row[7],
        })
    return output