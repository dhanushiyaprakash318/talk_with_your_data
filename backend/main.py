import json
import os
import sqlite3
import tempfile
import requests

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from faster_whisper import WhisperModel

# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "data", "app.db")

OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "llama3:8b"

app = FastAPI(title="Talk With Your Data API")

# -------------------------------------------------------
# CORS
# -------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------
# Whisper Model
# -------------------------------------------------------
whisper_model = WhisperModel("small", device="cpu")

# -------------------------------------------------------
# REQUEST MODEL
# -------------------------------------------------------
class ChatRequest(BaseModel):
    question: str

# -------------------------------------------------------
# RUN SQL
# -------------------------------------------------------
def run_sql_fetch(sql: str):
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="Database not found")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()

        columns = rows[0].keys() if rows else []
        data = [dict(row) for row in rows]

        return {"columns": list(columns), "rows": data}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        conn.close()

# -------------------------------------------------------
# SQL SAFETY
# -------------------------------------------------------
def is_safe_sql(sql: str) -> bool:
    sql = sql.lower()
    if not sql.startswith("select"):
        return False

    forbidden = [
        "insert ", "update ", "delete ", "drop ",
        "alter ", "create ", "pragma ", ";"
    ]
    return not any(word in sql for word in forbidden)

# -------------------------------------------------------
# ASK OLLAMA
# -------------------------------------------------------
def ask_model(prompt: str) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": True,
        "temperature": 0.0,
    }

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            stream=True,
            timeout=None
        )
        resp.raise_for_status()

        output = ""
        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line.decode())
            output += chunk.get("response", "")
            if chunk.get("done"):
                break

        return output.strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model error: {e}")

# -------------------------------------------------------
# SYSTEM PROMPT
# -------------------------------------------------------
SYSTEM_PROMPT = """
You are an expert SQLite analytics query generator.

RULES:
1. Output ONLY one valid SQLite SELECT query.
2. NEVER output explanations or comments.
3. Use ONLY valid columns from the schema.
4. NEVER use ":" anywhere in the SQL output.
5. NEVER generate aliases with ":" (such as month: revenue).
6. Use ONLY "AS alias" format.

-------------------------------------------------------
GENERAL TREND ANALYSIS RULES
-------------------------------------------------------
If user asks:

- "revenue trend"
- "revenue trend analysis"
- "show revenue trend"
- "trend analysis"
- "show revenue graph"
- "monthly revenue"
- "sales trend"
- "show analysis of revenue trend"

Then ALWAYS return this SQL pattern:

SELECT 
    strftime('%Y-%m', orders.order_date) AS month,
    SUM(orders.amount) AS revenue
FROM orders
GROUP BY month
ORDER BY month;

Never use colon ":" anywhere.
Never use CASE WHEN.
Never use JOIN unless summary table needed.
Never generate explanations — only raw SQL.


-------------------------------------------------------
SCHEMA
-------------------------------------------------------
TABLE orders:
- order_id
- customer_id
- product_id
- order_date
- amount

TABLE summary:
- id
- order_id
- quantity
- discount
- tax

-------------------------------------------------------
REVENUE DEFINITIONS
-------------------------------------------------------
Revenue ALWAYS means: SUM(orders.amount)
Sales count ALWAYS means: COUNT(orders.order_id)

NEVER generate these invalid columns:
orders.total, total_amount, revenue_amount, price, total

-------------------------------------------------------
DATE FILTERS
-------------------------------------------------------
This month:
    orders.order_date >= date('now','start of month')

Last month:
    orders.order_date >= date('now','start of month','-1 month')
    AND orders.order_date < date('now','start of month')

Last 6 months:
    orders.order_date >= date('now','-6 months')

-------------------------------------------------------
MONTH GROUPING
-------------------------------------------------------
strftime('%Y-%m', orders.order_date) AS month

-------------------------------------------------------
SUMMARY TABLE RULE
-------------------------------------------------------
If tax/discount/quantity is used → always join:

FROM summary
JOIN orders ON summary.order_id = orders.order_id

-------------------------------------------------------
COMPARISON QUESTIONS (MANDATORY RULE)
-------------------------------------------------------
For questions like:
- "compare last month revenue with this month"
- "difference between this month and last month"
- "compare revenue month over month"

Use EXACTLY this SQL pattern:

SELECT 
    'this_month' AS period,
    SUM(amount) AS revenue
FROM orders
WHERE orders.order_date >= date('now','start of month')

UNION ALL

SELECT
    'last_month' AS period,
    SUM(amount) AS revenue
FROM orders
WHERE orders.order_date >= date('now','start of month','-1 month')
  AND orders.order_date < date('now','start of month');

NEVER use CASE WHEN.
NEVER use concatenation.
NEVER use subqueries.

-------------------------------------------------------
UNCERTAIN QUESTIONS
-------------------------------------------------------
If unsure:
SELECT NULL WHERE 0;

Return ONLY RAW SQL.
-------------------------------------------------------
TAX ANALYSIS RULES
-------------------------------------------------------
If the user asks about:
- "tax trend"
- "tax analysis"
- "show tax trend analysis"
- "monthly tax"
- "tax graph"
- "trend of tax"

Then ALWAYS generate:

SELECT 
    strftime('%Y-%m', orders.order_date) AS month,
    SUM(summary.tax) AS tax
FROM summary
JOIN orders ON summary.order_id = orders.order_id
GROUP BY month
ORDER BY month;

Rules:
- Output column MUST be named "tax".
- Do NOT use revenue or amount.
- Never mix tax with revenue unless explicitly asked.

"""
# -------------------------------------------------------
# CLEAN SQL
# -------------------------------------------------------
def clean_sql(sql: str) -> str:
    sql = sql.replace("```sql", "").replace("```", "").strip()

    idx = sql.lower().find("select")
    if idx == -1:
        return "SELECT NULL WHERE 0"

    sql = sql[idx:]
    sql = sql.split(";")[0]

    sql = sql.replace("orders.total", "orders.amount")
    sql = sql.replace("total_amount", "amount")

    return sql.strip()

# -------------------------------------------------------
# INSIGHT
# -------------------------------------------------------
def generate_insight(rows):
    if len(rows) < 2:
        return ""

    values = []
    for r in rows:
        for v in r.values():
            if isinstance(v, (int, float)):
                values.append(v)
                break

    if len(values) < 2:
        return ""

    prev, last = values[-2], values[-1]
    if prev == 0:
        return ""

    change = ((last - prev) / prev) * 100

    if change > 20:
        return f"Revenue increased sharply (+{change:.2f}%)."
    if change < -20:
        return f"Revenue dropped significantly ({change:.2f}%)."
    return f"Revenue changed by {change:.2f}%."

# -------------------------------------------------------
# ANOMALY
# -------------------------------------------------------
def detect_anomaly(rows):
    nums = []
    for r in rows:
        for v in r.values():
            if isinstance(v, (int, float)):
                nums.append(v)
                break

    if len(nums) < 3:
        return ""

    avg = sum(nums) / len(nums)
    last = nums[-1]

    if last > avg * 1.5:
        return f"⚠️ Anomaly: Latest value {last} is much higher than average {avg:.2f}"
    if last < avg * 0.5:
        return f"⚠️ Anomaly: Latest value {last} is much lower than average {avg:.2f}"

    return ""

# -------------------------------------------------------
# CHAT ENDPOINT
# -------------------------------------------------------
@app.post("/chat")
def chat(req: ChatRequest):
    prompt = f"{SYSTEM_PROMPT}\nUser Question: {req.question}\nSQL:"

    llm_output = ask_model(prompt)
    sql = clean_sql(llm_output)

    print("LLM OUTPUT:", llm_output)
    print("CLEAN SQL:", sql)

    if not is_safe_sql(sql):
        sql = "SELECT NULL WHERE 0"

    result = run_sql_fetch(sql)

    return {
        "generated_sql": sql,
        "data": result,
        "insight": generate_insight(result["rows"]),
        "anomaly": detect_anomaly(result["rows"]),
        "message": "Success"
    }

# -------------------------------------------------------
# SPEECH → TEXT
# -------------------------------------------------------
@app.post("/speech_to_text")
async def speech_to_text(file: UploadFile = File(...)):
    try:
        audio_bytes = await file.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        segments, _ = whisper_model.transcribe(tmp_path)
        text = " ".join(seg.text for seg in segments)

        return {"text": text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
