import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_supported_languages():
    """Verify that supported languages endpoint returns valid language list with readable display names and runtime IDs."""
    response = client.get("/api/interviews/languages")
    assert response.status_code == 200
    data = response.json()
    assert "languages" in data
    languages = data["languages"]
    assert len(languages) >= 10

    # Build lookup by id/key
    by_id = {l["id"]: l for l in languages}

    # Required core languages
    required = ["python", "javascript", "typescript", "java", "c", "cpp", "csharp", "go", "rust", "sql"]
    for req_id in required:
        assert req_id in by_id, f"Expected runtime '{req_id}' in supported languages"
        lang = by_id[req_id]
        assert lang["name"], f"Language '{req_id}' missing name"
        assert lang["version"], f"Language '{req_id}' missing version"
        assert f"— ({lang['version']})" in lang["display_name"], f"Invalid display_name for '{req_id}': {lang['display_name']}"

    # Verify specific readable names
    assert by_id["python"]["name"] == "Python 3"
    assert by_id["python"]["version"] == "3.10.0"
    assert by_id["python"]["display_name"] == "Python 3 — (3.10.0)"

    assert by_id["javascript"]["name"] == "JavaScript (Node.js)"
    assert by_id["javascript"]["version"] == "18.15.0"
    assert by_id["javascript"]["display_name"] == "JavaScript (Node.js) — (18.15.0)"

    assert by_id["cpp"]["name"] == "C++"
    assert by_id["cpp"]["display_name"] == "C++ — (10.2.0)"

    assert by_id["java"]["name"] == "Java"
    assert by_id["java"]["display_name"] == "Java — (15.0.2)"

    assert by_id["sql"]["name"] == "SQL"
    assert by_id["sql"]["is_sql"] is True



def test_sql_schema_metadata():
    """Verify that SQL sandbox fixtures return valid table schemas and sample rows."""
    response = client.get("/api/interviews/sql-schema/employees_departments")
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "employees_departments"
    assert "tables" in data
    table_names = [t["table_name"] for t in data["tables"]]
    assert "departments" in table_names
    assert "employees" in table_names
    assert len(data["tables"][0]["sample_rows"]) > 0


def test_execute_sql_query_success():
    """Verify valid candidate SQL query executes inside isolated in-memory SQLite sandbox."""
    payload = {
        "query": "SELECT emp_name, salary FROM employees WHERE salary > 100000 ORDER BY salary DESC;",
        "question_id": "employees_departments",
    }
    response = client.post("/api/interviews/execute-sql", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["columns"] == ["emp_name", "salary"]
    assert data["row_count"] >= 4
    assert data["error"] is None
    # Highest earner is Alice Chen
    assert data["rows"][0][0] == "Alice Chen"
    assert data["rows"][0][1] == 145000


def test_execute_sql_query_syntax_error():
    """Verify SQL syntax error is captured and returned gracefully without 500 error."""
    payload = {
        "query": "SELEC * FORM invalid_table;",
        "question_id": "employees_departments",
    }
    response = client.post("/api/interviews/execute-sql", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "syntax_error"
    assert "Operational Error" in data["error"]


def test_execute_sql_disallow_destructive():
    """Verify destructive statements like DROP/ALTER are blocked in sandbox mode."""
    payload = {
        "query": "DROP TABLE employees;",
        "question_id": "employees_departments",
    }
    response = client.post("/api/interviews/execute-sql", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "not permitted" in data["error"]


def test_submit_sql_solution_evaluation():
    """Verify candidate SQL query submission and validation."""
    payload = {
        "question_id": "employees_departments",
        "query": "SELECT dept_name, count(*) as emp_count FROM departments d JOIN employees e ON d.dept_id = e.dept_id GROUP BY dept_name;",
    }
    response = client.post("/api/interviews/submit-sql", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "evaluated"
    assert data["is_correct"] is True
    assert data["row_count"] > 0


def test_code_execution_unsupported_language():
    """Verify unsupported language requests return clean error without crashing."""
    payload = {
        "language": "nonexistent_lang",
        "code": "print('hello')",
        "stdin": "",
    }
    response = client.post("/api/interviews/execute-code", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "not supported" in data["error"]
