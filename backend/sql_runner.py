from sqlalchemy import text

ALLOWED_TABLES = {
    "appointment_trans_summary",
    "appointment_transactions",
    "billing_paymode",
    "account_master"
}

def is_safe_sql(sql: str) -> bool:
    sql_lower = sql.lower()
    if not sql_lower.startswith("select"):
        return False

    for word in ["drop", "delete", "update", "insert", "alter"]:
        if word in sql_lower:
            return False

    return any(tbl in sql_lower for tbl in ALLOWED_TABLES)


def run_sql(db, sql: str):
    if not is_safe_sql(sql):
        raise ValueError("Unsafe SQL detected")

    result = db.execute(text(sql))
    rows = result.fetchall()
    columns = result.keys()

    return {
        "columns": list(columns),
        "rows": [dict(zip(columns, row)) for row in rows]
    }
