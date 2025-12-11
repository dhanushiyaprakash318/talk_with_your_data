import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import os
import requests
from fastapi.middleware.cors import CORSMiddleware


# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")
OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "llama3.1:8b"

app = FastAPI(title="Talk With Your Data API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        raise HTTPException(status_code=500, detail=f"Database missing at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()

        cols = rows[0].keys() if rows else []
        data = [dict(row) for row in rows]
        return {"columns": list(cols), "rows": data}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        conn.close()


# -------------------------------------------------------
# SAFETY CHECK
# -------------------------------------------------------
def is_safe_sql(sql: str) -> bool:
    sql_low = sql.lower()

    if not sql_low.startswith("select"):
        return False

    banned = [
        "insert ", "update ", "delete ", "drop ", "alter ",
        "create ", "replace ", "attach ", "detach ", "pragma ",
        ";"
    ]

    return not any(b in sql_low for b in banned)


# -------------------------------------------------------
# LLM CALL
# -------------------------------------------------------
def ask_model(prompt: str) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": True,
        "temperature": 0.0,
    }

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            stream=True
        )
        response.raise_for_status()

        out = ""
        for line in response.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line.decode())
                if "response" in chunk:
                    out += chunk["response"]
                if chunk.get("done"):
                    break
            except:
                continue

        return out.strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model error: {e}")


# -------------------------------------------------------
# SYSTEM PROMPT (MOST IMPORTANT PART)
# -------------------------------------------------------
SYSTEM_PROMPT = """
You are an expert SQLite analytics query generator.

RULES:
1. Output ONLY one valid SQLite SELECT query.
2. NEVER output explanations or comments.
3. Use ONLY valid columns from the schema.

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
"""


# -------------------------------------------------------
# SQL CLEANER
# -------------------------------------------------------
def clean_sql(sql: str) -> str:
    sql = sql.replace("```sql", "").replace("```", "").strip()

    idx = sql.lower().find("select")
    if idx == -1:
        return "SELECT NULL WHERE 0"

    sql = sql[idx:]

    if ";" in sql:
        sql = sql.split(";")[0]

    # Auto-repair invalid columns
    sql = sql.replace("orders.total_amount", "orders.amount")
    sql = sql.replace("orders.total", "orders.amount")
    sql = sql.replace("total_amount", "amount")
    sql = sql.replace("revenue", "amount")

    return sql.strip()


# -------------------------------------------------------
# INSIGHT GENERATOR
# -------------------------------------------------------
def generate_insight(sql: str, rows):
    if not rows:
        return ""

    numbers = []
    for r in rows:
        for v in r.values():
            try:
                numbers.append(float(v))
                break
            except:
                continue

    if len(numbers) < 2:
        return ""

    last = numbers[-1]
    prev = numbers[-2]

    if prev == 0:
        return ""

    change = ((last - prev) / prev) * 100

    if change > 20:
        return f"Revenue increased sharply (+{change:.2f}%)."
    elif change < -20:
        return f"Revenue dropped significantly ({change:.2f}%)."
    else:
        return f"Revenue changed by {change:.2f}% compared to previous period."


# -------------------------------------------------------
# ANOMALY DETECTION
# -------------------------------------------------------
def detect_anomaly(rows):
    if not rows:
        return ""

    nums = []

    for r in rows:
        for v in r.values():
            try:
                nums.append(float(v))
                break
            except:
                continue

    if len(nums) < 3:
        return ""

    avg = sum(nums) / len(nums)
    last = nums[-1]

    if last > avg * 1.5:
        return f"⚠️ Anomaly: Latest value {last} is much HIGHER than avg {avg:.2f}"
    if last < avg * 0.5:
        return f"⚠️ Anomaly: Latest value {last} is much LOWER than avg {avg:.2f}"

    return ""


# -------------------------------------------------------
# MAIN API ENDPOINT
# -------------------------------------------------------
@app.post("/chat")
def chat(req: ChatRequest):
    user_q = req.question.strip()

    prompt = f"{SYSTEM_PROMPT}\nUser Question: {user_q}\nReturn ONLY SQL:"

    llm_output = ask_model(prompt)

    sql = clean_sql(llm_output)

    if not is_safe_sql(sql):
        sql = "SELECT NULL WHERE 0"

    result = run_sql_fetch(sql)

    insight = generate_insight(sql, result["rows"])
    anomaly = detect_anomaly(result["rows"])

    return {
        "generated_sql": sql,
        "data": result,
        "insight": insight,
        "anomaly": anomaly,
        "message": "Success"
    }
