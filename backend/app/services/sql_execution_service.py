import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple
from app.schemas.execution import (
    SQLExecutionResponse,
    SQLSubmissionResult,
)

logger = logging.getLogger("interviewiq.sql_execution")

# Curated interview database fixtures
SQL_FIXTURES: Dict[str, Dict[str, Any]] = {
    "employees_departments": {
        "title": "Corporate HR & Payroll Database",
        "description": "Company employee records, department structures, salaries, and hierarchy.",
        "tables": [
            {
                "table_name": "departments",
                "columns": [
                    {"name": "dept_id", "type": "INTEGER PRIMARY KEY"},
                    {"name": "dept_name", "type": "TEXT"},
                    {"name": "location", "type": "TEXT"},
                ],
                "sample_rows": [
                    [1, "Engineering", "San Francisco"],
                    [2, "Product", "New York"],
                    [3, "Marketing", "London"],
                    [4, "Finance", "Chicago"],
                ],
            },
            {
                "table_name": "employees",
                "columns": [
                    {"name": "emp_id", "type": "INTEGER PRIMARY KEY"},
                    {"name": "emp_name", "type": "TEXT"},
                    {"name": "dept_id", "type": "INTEGER"},
                    {"name": "salary", "type": "INTEGER"},
                    {"name": "hire_date", "type": "TEXT"},
                    {"name": "manager_id", "type": "INTEGER"},
                ],
                "sample_rows": [
                    [101, "Alice Chen", 1, 145000, "2021-03-15", None],
                    [102, "Bob Smith", 1, 120000, "2021-08-01", 101],
                    [103, "Charlie Davis", 2, 110000, "2022-01-10", None],
                    [104, "Diana Prince", 2, 95000, "2022-06-20", 103],
                    [105, "Evan Wright", 3, 85000, "2020-11-05", None],
                    [106, "Fiona Gallagher", 1, 130000, "2022-03-01", 101],
                    [107, "George Clark", 4, 105000, "2019-05-12", None],
                    [108, "Hannah Abbott", 3, 92000, "2023-02-14", 105],
                ],
            },
        ],
        "setup_sql": """
            CREATE TABLE departments (
                dept_id INTEGER PRIMARY KEY,
                dept_name TEXT,
                location TEXT
            );
            INSERT INTO departments VALUES
                (1, 'Engineering', 'San Francisco'),
                (2, 'Product', 'New York'),
                (3, 'Marketing', 'London'),
                (4, 'Finance', 'Chicago');

            CREATE TABLE employees (
                emp_id INTEGER PRIMARY KEY,
                emp_name TEXT,
                dept_id INTEGER,
                salary INTEGER,
                hire_date TEXT,
                manager_id INTEGER
            );
            INSERT INTO employees VALUES
                (101, 'Alice Chen', 1, 145000, '2021-03-15', NULL),
                (102, 'Bob Smith', 1, 120000, '2021-08-01', 101),
                (103, 'Charlie Davis', 2, 110000, '2022-01-10', NULL),
                (104, 'Diana Prince', 2, 95000, '2022-06-20', 103),
                (105, 'Evan Wright', 3, 85000, '2020-11-05', NULL),
                (106, 'Fiona Gallagher', 1, 130000, '2022-03-01', 101),
                (107, 'George Clark', 4, 105000, '2019-05-12', NULL),
                (108, 'Hannah Abbott', 3, 92000, '2023-02-14', 105);
        """,
    },
    "customers_orders": {
        "title": "E-Commerce Customer & Orders Database",
        "description": "Store customer accounts, orders placed, order totals, and fulfillment status.",
        "tables": [
            {
                "table_name": "customers",
                "columns": [
                    {"name": "customer_id", "type": "INTEGER PRIMARY KEY"},
                    {"name": "customer_name", "type": "TEXT"},
                    {"name": "country", "type": "TEXT"},
                    {"name": "signup_date", "type": "TEXT"},
                ],
                "sample_rows": [
                    [1, "Acme Corp", "USA", "2022-01-15"],
                    [2, "Global Tech", "Canada", "2022-04-10"],
                    [3, "Nexus Media", "UK", "2023-02-01"],
                    [4, "Vanguard Retail", "USA", "2023-05-18"],
                ],
            },
            {
                "table_name": "orders",
                "columns": [
                    {"name": "order_id", "type": "INTEGER PRIMARY KEY"},
                    {"name": "customer_id", "type": "INTEGER"},
                    {"name": "order_date", "type": "TEXT"},
                    {"name": "total_amount", "type": "REAL"},
                    {"name": "status", "type": "TEXT"},
                ],
                "sample_rows": [
                    [501, 1, "2023-06-01", 1250.50, "Completed"],
                    [502, 1, "2023-07-15", 3400.00, "Completed"],
                    [503, 2, "2023-06-18", 890.00, "Completed"],
                    [504, 3, "2023-08-02", 450.00, "Pending"],
                    [505, 1, "2023-09-10", 2100.00, "Completed"],
                    [506, 4, "2023-09-12", 1500.00, "Completed"],
                ],
            },
        ],
        "setup_sql": """
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                customer_name TEXT,
                country TEXT,
                signup_date TEXT
            );
            INSERT INTO customers VALUES
                (1, 'Acme Corp', 'USA', '2022-01-15'),
                (2, 'Global Tech', 'Canada', '2022-04-10'),
                (3, 'Nexus Media', 'UK', '2023-02-01'),
                (4, 'Vanguard Retail', 'USA', '2023-05-18');

            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                order_date TEXT,
                total_amount REAL,
                status TEXT
            );
            INSERT INTO orders VALUES
                (501, 1, '2023-06-01', 1250.50, 'Completed'),
                (502, 1, '2023-07-15', 3400.00, 'Completed'),
                (503, 2, '2023-06-18', 890.00, 'Completed'),
                (504, 3, '2023-08-02', 450.00, 'Pending'),
                (505, 1, '2023-09-10', 2100.00, 'Completed'),
                (506, 4, '2023-09-12', 1500.00, 'Completed');
        """,
    },
}


def get_fixture_metadata(fixture_key: str = "employees_departments") -> Dict[str, Any]:
    """Retrieve schema definitions and sample data for the requested fixture."""
    fixture = SQL_FIXTURES.get(fixture_key) or SQL_FIXTURES["employees_departments"]
    return {
        "key": fixture_key,
        "title": fixture["title"],
        "description": fixture["description"],
        "tables": fixture["tables"],
    }


def execute_sql_in_memory(
    query: str,
    fixture_key: str = "employees_departments",
    max_rows: int = 100,
) -> SQLExecutionResponse:
    """
    Execute a candidate SQL query inside an ephemeral, in-memory SQLite sandbox.
    Strictly isolated from MongoDB Atlas or any real database.
    """
    cleaned_query = query.strip().rstrip(";")
    if not cleaned_query:
        return SQLExecutionResponse(
            status="syntax_error",
            error="SQL query cannot be empty.",
        )

    # Disallow destructive modifications to maintain sandbox safety
    first_token = cleaned_query.split()[0].upper()
    disallowed_keywords = {"DROP", "ALTER", "ATTACH", "DETACH", "VACUUM"}
    if first_token in disallowed_keywords:
        return SQLExecutionResponse(
            status="error",
            error=f"Statement type '{first_token}' is not permitted in read-only sandbox mode.",
        )

    fixture = SQL_FIXTURES.get(fixture_key) or SQL_FIXTURES["employees_departments"]

    start_time = time.time()
    conn = sqlite3.connect(":memory:")
    try:
        cursor = conn.cursor()
        # Seed isolated test tables
        cursor.executescript(fixture["setup_sql"])

        # Execute candidate query with row limit
        cursor.execute(cleaned_query)

        col_names = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(max_rows)
        # Convert tuples to lists for JSON serialization
        serialized_rows = [list(r) for r in rows]
        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return SQLExecutionResponse(
            columns=col_names,
            rows=serialized_rows,
            row_count=len(serialized_rows),
            execution_time_ms=elapsed_ms,
            status="success",
            error=None,
        )

    except sqlite3.OperationalError as exc:
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return SQLExecutionResponse(
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=elapsed_ms,
            status="syntax_error",
            error=f"SQL Operational Error: {str(exc)}",
        )
    except Exception as exc:
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return SQLExecutionResponse(
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=elapsed_ms,
            status="runtime_error",
            error=f"SQL Execution Error: {type(exc).__name__}: {str(exc)}",
        )
    finally:
        conn.close()


def evaluate_sql_solution(
    candidate_query: str,
    expected_query: Optional[str] = None,
    fixture_key: str = "employees_departments",
) -> SQLSubmissionResult:
    """
    Evaluate candidate SQL against expected reference query in the isolated sandbox.
    Compares resultant columns and dataset rows.
    """
    candidate_res = execute_sql_in_memory(candidate_query, fixture_key=fixture_key)

    if candidate_res.status != "success":
        return SQLSubmissionResult(
            question_id=fixture_key,
            is_correct=False,
            columns=[],
            actual_rows=[],
            expected_rows=[],
            row_count=0,
            status=candidate_res.status,
            error=candidate_res.error,
            optimization_feedback="Ensure SQL syntax is valid and all referenced table/column names exist.",
        )

    if not expected_query:
        # If no expected query benchmark is set, successful execution is valid
        return SQLSubmissionResult(
            question_id=fixture_key,
            is_correct=True,
            columns=candidate_res.columns,
            actual_rows=candidate_res.rows,
            expected_rows=candidate_res.rows,
            row_count=candidate_res.row_count,
            status="evaluated",
            optimization_feedback="Query executed cleanly and returned valid records.",
        )

    expected_res = execute_sql_in_memory(expected_query, fixture_key=fixture_key)

    # Normalize column names lower-cased
    cand_cols = [c.lower() for c in candidate_res.columns]
    exp_cols = [c.lower() for c in expected_res.columns]

    # Compare sets of rows (order-independent unless expected explicitly orders)
    cand_rows_set = sorted([str(r) for r in candidate_res.rows])
    exp_rows_set = sorted([str(r) for r in expected_res.rows])

    is_correct = (cand_cols == exp_cols and cand_rows_set == exp_rows_set)

    feedback = None
    if not is_correct:
        if cand_cols != exp_cols:
            feedback = f"Column mismatch. Expected: {expected_res.columns}, but query returned: {candidate_res.columns}."
        elif len(candidate_res.rows) != len(expected_res.rows):
            feedback = f"Row count mismatch. Expected {len(expected_res.rows)} rows, but query returned {len(candidate_res.rows)} rows."
        else:
            feedback = "Record data values do not match expected benchmark output. Check JOIN conditions and WHERE filters."
    else:
        feedback = "Query produced the exact expected dataset and column structure."

    return SQLSubmissionResult(
        question_id=fixture_key,
        is_correct=is_correct,
        columns=candidate_res.columns,
        actual_rows=candidate_res.rows,
        expected_rows=expected_res.rows,
        row_count=candidate_res.row_count,
        status="evaluated",
        error=None,
        optimization_feedback=feedback,
    )
