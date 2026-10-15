from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CodeExecutionRequest(BaseModel):
    """Request payload to execute code against custom input."""

    language: str = Field(..., description="Programming language key, e.g., 'python', 'javascript', 'cpp'")
    code: str = Field(..., min_length=1, max_length=50000, description="Source code to execute")
    stdin: Optional[str] = Field(default="", max_length=10000, description="Standard input provided to the program")
    question_id: Optional[str] = Field(default=None, description="Optional question context ID")
    function_name: Optional[str] = Field(default=None, description="Optional target function name")
    session_id: Optional[str] = Field(default=None, description="Optional session context ID")


class CodeExecutionResponse(BaseModel):
    """Output from executing code in isolated sandbox."""

    stdout: str = Field(default="")
    stderr: str = Field(default="")
    output: str = Field(default="")
    exit_code: int = Field(default=0)
    execution_time_ms: Optional[float] = Field(default=None)
    memory_kb: Optional[float] = Field(default=None)
    status: str = Field(default="success", description="'success', 'runtime_error', 'compilation_error', 'timeout', 'error'")
    error: Optional[str] = None


class TestCase(BaseModel):
    """Structured test case definition for DSA coding questions."""

    id: str = Field(..., description="Test case identifier, e.g., 'tc_1'")
    input: str = Field(default="", description="Standard input string or argument representation")
    expected_output: str = Field(..., description="Expected output string")
    is_hidden: bool = Field(default=False, description="Whether this is a private/hidden test case")
    comparison_policy: Optional[str] = Field(default=None, description="Optional override comparison policy")
    float_tolerance: Optional[float] = Field(default=None, description="Optional float tolerance override")


class TestCaseResult(BaseModel):
    """Evaluation result for an individual test case."""

    test_case_id: str
    input: str
    expected_output: str
    actual_output: str
    passed: bool
    is_hidden: bool = False
    execution_time_ms: Optional[float] = None
    error: Optional[str] = None
    comparison_policy: Optional[str] = None


class SubmitCodeSolutionRequest(BaseModel):
    """Candidate code submission for evaluation against test cases."""

    question_id: str = Field(..., description="Question ID being solved")
    language: str = Field(..., description="Programming language")
    code: str = Field(..., min_length=1, max_length=50000, description="Complete solution code")
    verbal_explanation: Optional[str] = Field(default=None, max_length=5000, description="Optional spoken/written explanation")
    session_id: Optional[str] = Field(default=None, description="Active session ID to retrieve question test cases")
    test_cases: Optional[List[TestCase]] = Field(default=None, description="Explicit test cases if provided")
    comparison_policy: Optional[str] = Field(default=None, description="Optional comparison policy for the submission")
    float_tolerance: Optional[float] = Field(default=None, description="Optional numerical tolerance")


class CodeSubmissionResult(BaseModel):
    """Evaluation outcome for code submitted against question test cases."""

    question_id: str
    language: str
    total_tests: int
    passed_tests: int
    all_passed: bool
    results: List[TestCaseResult]
    status: str = Field(default="evaluated")
    compilation_error: Optional[str] = None
    estimated_time_complexity: Optional[str] = None
    estimated_space_complexity: Optional[str] = None


class SQLExecutionRequest(BaseModel):
    """Candidate SQL query execution request."""

    query: str = Field(..., min_length=1, max_length=10000, description="SQL query to execute in isolated sandbox")
    question_id: Optional[str] = Field(default=None, description="Question context to determine active schema fixture")


class SQLExecutionResponse(BaseModel):
    """Result of running SQL query in isolated SQLite sandbox."""

    columns: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    status: str = Field(default="success", description="'success', 'syntax_error', 'runtime_error', 'error'")
    error: Optional[str] = None


class SubmitSQLSolutionRequest(BaseModel):
    """Submission of candidate SQL query against question benchmarks."""

    question_id: str
    query: str = Field(..., min_length=1, max_length=10000)
    verbal_explanation: Optional[str] = Field(default=None, max_length=5000)
    session_id: Optional[str] = Field(default=None, description="Active session ID to retrieve expected query")
    expected_query: Optional[str] = Field(default=None, description="Benchmark query for evaluation")
    fixture_key: Optional[str] = Field(default=None, description="Fixture key if known")


class SQLSubmissionResult(BaseModel):
    """Result of evaluating SQL query against expected result set."""

    question_id: str
    is_correct: bool
    columns: List[str]
    actual_rows: List[List[Any]]
    expected_rows: List[List[Any]]
    row_count: int
    status: str
    error: Optional[str] = None
    optimization_feedback: Optional[str] = None
