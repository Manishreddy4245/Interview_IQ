import ast
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple
from app.schemas.execution import (
    CodeExecutionRequest,
    CodeExecutionResponse,
    TestCase,
    TestCaseResult,
    CodeSubmissionResult,
)

from app.core.config import settings

logger = logging.getLogger("interviewiq.code_execution")


def _find_binary(*candidates: str) -> Optional[str]:
    """Find binary executable across common system installation locations."""
    for cand in candidates:
        if not cand:
            continue
        which = shutil.which(cand)
        if which and os.path.exists(which):
            return which
        if os.path.exists(cand):
            return cand
    return None


# Local compiler / runtime binary discovery
PYTHON_BIN = sys.executable or _find_binary("python", "python3")
NODE_BIN = _find_binary(
    "node",
    r"C:\Program Files\nodejs\node.exe",
    r"C:\Program Files (x86)\nodejs\node.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\node\node.exe"),
)
GCC_BIN = _find_binary(
    "gcc",
    r"C:\MinGW\bin\gcc.exe",
    r"C:\msys64\mingw64\bin\gcc.exe",
    r"C:\Program Files\Git\usr\bin\gcc.exe",
)
GPP_BIN = _find_binary(
    "g++",
    r"C:\MinGW\bin\g++.exe",
    r"C:\msys64\mingw64\bin\g++.exe",
)
JAVAC_BIN = _find_binary(
    "javac",
    r"C:\Program Files\Common Files\Oracle\Java\javapath\javac.exe",
    r"C:\Program Files\Java\jdk-21\bin\javac.exe",
    r"C:\Program Files\Java\jdk-17\bin\javac.exe",
    r"C:\Program Files\Java\jdk-11\bin\javac.exe",
)
JAVA_BIN = _find_binary(
    "java",
    r"C:\Program Files\Common Files\Oracle\Java\javapath\java.exe",
    r"C:\Program Files\Java\jdk-21\bin\java.exe",
    r"C:\Program Files\Java\jdk-17\bin\java.exe",
    r"C:\Program Files\Java\jdk-11\bin\java.exe",
)

# Judge0 language ID mappings (Judge0 CE standard)
JUDGE0_LANGUAGE_IDS: Dict[str, int] = {
    "python": 71,       # Python (3.8.1+)
    "javascript": 63,   # JavaScript (Node.js 12.14.0+)
    "typescript": 74,   # TypeScript (3.7.4+)
    "java": 62,         # Java (OpenJDK 13.0.1+)
    "cpp": 54,          # C++ (GCC 9.2.0+)
    "c": 50,            # C (GCC 9.2.0+)
    "csharp": 51,       # C# (Mono 6.6.0.161)
    "go": 60,           # Go (1.13.5)
    "rust": 73,         # Rust (1.40.0)
    "kotlin": 78,       # Kotlin (1.3.70)
    "php": 68,          # PHP (7.4.1)
    "ruby": 72,         # Ruby (2.7.0)
    "swift": 83,        # Swift (5.2.3)
    "scala": 81,        # Scala (2.13.2)
}

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILD_CACHE_DIR = os.path.join(BACKEND_DIR, ".build_cache")
try:
    os.makedirs(BUILD_CACHE_DIR, exist_ok=True)
except Exception:
    BUILD_CACHE_DIR = None

# Supported interview languages mapped to Piston runtime identifiers
LANGUAGE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "python": {
        "name": "Python 3",
        "piston_lang": "python",
        "version": "3.10.0",
        "file_name": "solution.py",
        "starter_template": (
            "import sys\n\n"
            "def solve():\n"
            "    # Read input from stdin\n"
            "    input_data = sys.stdin.read().split()\n"
            "    if not input_data:\n"
            "        return\n"
            "    \n"
            "    # TODO: Implement your solution here\n"
            "    print(' '.join(input_data))\n\n"
            "if __name__ == '__main__':\n"
            "    solve()\n"
        ),
    },
    "javascript": {
        "name": "JavaScript (Node.js)",
        "piston_lang": "javascript",
        "version": "18.15.0",
        "file_name": "solution.js",
        "starter_template": (
            "const fs = require('fs');\n\n"
            "function solve() {\n"
            "    const input = fs.readFileSync(0, 'utf-8').trim();\n"
            "    // TODO: Implement your solution here\n"
            "    console.log(input);\n"
            "}\n\n"
            "solve();\n"
        ),
    },
    "typescript": {
        "name": "TypeScript",
        "piston_lang": "typescript",
        "version": "5.0.3",
        "file_name": "solution.ts",
        "starter_template": (
            "import * as fs from 'fs';\n\n"
            "function solve(): void {\n"
            "    const input: string = fs.readFileSync(0, 'utf-8').trim();\n"
            "    // TODO: Implement your solution here\n"
            "    console.log(input);\n"
            "}\n\n"
            "solve();\n"
        ),
    },
    "java": {
        "name": "Java",
        "piston_lang": "java",
        "version": "15.0.2",
        "file_name": "Main.java",
        "starter_template": (
            "import java.util.Scanner;\n\n"
            "public class Main {\n"
            "    public static void main(String[] args) {\n"
            "        Scanner scanner = new Scanner(System.in);\n"
            "        // TODO: Implement your solution here\n"
            "        while (scanner.hasNext()) {\n"
            "            System.out.println(scanner.next());\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
    },
    "cpp": {
        "name": "C++",
        "piston_lang": "c++",
        "version": "10.2.0",
        "file_name": "solution.cpp",
        "starter_template": (
            "#include <iostream>\n"
            "#include <vector>\n"
            "#include <string>\n\n"
            "using namespace std;\n\n"
            "int main() {\n"
            "    ios_base::sync_with_stdio(false);\n"
            "    cin.tie(NULL);\n"
            "    // TODO: Implement your solution here\n"
            "    string token;\n"
            "    while (cin >> token) {\n"
            "        cout << token << \"\\n\";\n"
            "    }\n"
            "    return 0;\n"
            "}\n"
        ),
    },
    "c": {
        "name": "C",
        "piston_lang": "c",
        "version": "10.2.0",
        "file_name": "solution.c",
        "starter_template": (
            "#include <stdio.h>\n\n"
            "int main() {\n"
            "    // TODO: Implement your solution here\n"
            "    char buffer[256];\n"
            "    while (scanf(\"%255s\", buffer) == 1) {\n"
            "        printf(\"%s\\n\", buffer);\n"
            "    }\n"
            "    return 0;\n"
            "}\n"
        ),
    },
    "csharp": {
        "name": "C#",
        "piston_lang": "csharp",
        "version": "6.12.0",
        "file_name": "Solution.cs",
        "starter_template": (
            "using System;\n\n"
            "public class Program {\n"
            "    public static void Main() {\n"
            "        string line;\n"
            "        while ((line = Console.ReadLine()) != null) {\n"
            "            Console.WriteLine(line);\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
    },
    "go": {
        "name": "Go",
        "piston_lang": "go",
        "version": "1.16.2",
        "file_name": "main.go",
        "starter_template": (
            "package main\n\n"
            "import (\n"
            "\t\"bufio\"\n"
            "\t\"fmt\"\n"
            "\t\"os\"\n"
            ")\n\n"
            "func main() {\n"
            "\tscanner := bufio.NewScanner(os.Stdin)\n"
            "\tfor scanner.Scan() {\n"
            "\t\tfmt.Println(scanner.Text())\n"
            "\t}\n"
            "}\n"
        ),
    },
    "rust": {
        "name": "Rust",
        "piston_lang": "rust",
        "version": "1.68.2",
        "file_name": "main.rs",
        "starter_template": (
            "use std::io::{self, BufRead};\n\n"
            "fn main() {\n"
            "    let stdin = io::stdin();\n"
            "    for line in stdin.lock().lines() {\n"
            "        if let Ok(l) = line {\n"
            "            println!(\"{}\", l);\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
    },
    "kotlin": {
        "name": "Kotlin",
        "piston_lang": "kotlin",
        "version": "1.8.20",
        "file_name": "Solution.kt",
        "starter_template": (
            "import java.util.Scanner\n\n"
            "fun main() {\n"
            "    val scanner = Scanner(System.`in`)\n"
            "    while (scanner.hasNext()) {\n"
            "        println(scanner.next())\n"
            "    }\n"
            "}\n"
        ),
    },
    "php": {
        "name": "PHP",
        "piston_lang": "php",
        "version": "8.2.3",
        "file_name": "solution.php",
        "starter_template": (
            "<?php\n"
            "// TODO: Implement your solution here\n"
            "while ($line = fgets(STDIN)) {\n"
            "    echo trim($line) . \"\\n\";\n"
            "}\n"
        ),
    },
    "ruby": {
        "name": "Ruby",
        "piston_lang": "ruby",
        "version": "3.0.1",
        "file_name": "solution.rb",
        "starter_template": (
            "# TODO: Implement your solution here\n"
            "ARGF.each_line do |line|\n"
            "  puts line.strip\n"
            "end\n"
        ),
    },
    "swift": {
        "name": "Swift",
        "piston_lang": "swift",
        "version": "5.3.3",
        "file_name": "solution.swift",
        "starter_template": (
            "import Foundation\n\n"
            "while let line = readLine() {\n"
            "    print(line)\n"
            "}\n"
        ),
    },
    "scala": {
        "name": "Scala",
        "piston_lang": "scala",
        "version": "3.2.2",
        "file_name": "Solution.scala",
        "starter_template": (
            "import scala.io.StdIn\n\n"
            "object Solution {\n"
            "  def main(args: Array[String]): Unit = {\n"
            "    var line = StdIn.readLine()\n"
            "    while (line != null) {\n"
            "      println(line)\n"
            "      line = StdIn.readLine()\n"
            "    }\n"
            "  }\n"
            "}\n"
        ),
    },
}


def get_supported_languages() -> List[Dict[str, Any]]:
    """Return list of supported languages with display names, runtime IDs, and default templates."""
    languages: List[Dict[str, Any]] = []
    for key, cfg in LANGUAGE_CONFIGS.items():
        languages.append({
            "id": key,
            "key": key,
            "name": cfg["name"],
            "label": cfg["name"],
            "display_name": f"{cfg['name']} — ({cfg['version']})",
            "version": cfg["version"],
            "piston_lang": cfg["piston_lang"],
            "file_name": cfg["file_name"],
            "starter_template": cfg["starter_template"],
            "monaco_language": "cpp" if key == "cpp" else "csharp" if key == "csharp" else key,
            "is_sql": False,
        })

    # Include SQL runtime if in-memory SQLite sandbox is configured
    try:
        import sqlite3
        languages.append({
            "id": "sql",
            "key": "sql",
            "name": "SQL",
            "label": "SQL",
            "display_name": f"SQL — ({sqlite3.sqlite_version})",
            "version": sqlite3.sqlite_version,
            "piston_lang": "sqlite3",
            "file_name": "query.sql",
            "starter_template": "-- Write your SQL query here\nSELECT * FROM employees LIMIT 10;\n",
            "monaco_language": "sql",
            "is_sql": True,
        })
    except Exception as exc:
        logger.warning("SQLite sandbox runtime unavailable: %s", exc)

    return languages


def normalize_output(s: str) -> str:
    """Normalize output string for robust comparison across JSON arrays, whitespace, and line breaks."""
    cleaned = (s or "").strip().replace("\r\n", "\n")
    try:
        data = json.loads(cleaned)
        return json.dumps(data, separators=(",", ":")).lower()
    except Exception:
        pass
    if cleaned.lower() in ("true", "false"):
        return cleaned.lower()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        return cleaned.replace(", ", ",").lower()
    return cleaned


def parse_output_value(raw: str) -> Tuple[Any, bool]:
    """
    Parse a raw stdout or expected string into a canonical Python data structure.
    Returns (parsed_value, is_structured).
    Handles:
    - Booleans ('true', 'false', 'True', 'False')
    - Integers ('42', '-7')
    - Floats ('3.14', '-0.05')
    - JSON arrays/objects ('[1,2,3]', '{"a": 1}')
    - Python literals (tuples, sets, nested lists)
    - Fallback: stripped string
    """
    cleaned = (raw or "").strip().replace("\r\n", "\n")
    if not cleaned:
        return "", False

    # Check for boolean primitive
    if cleaned.lower() in ("true", "false"):
        return (cleaned.lower() == "true"), True

    # Check for integer primitive
    if re.match(r"^-?\d+$", cleaned):
        try:
            return int(cleaned), True
        except Exception:
            pass

    # Check for float primitive
    if re.match(r"^-?\d+\.\d+(?:[eE][-+]?\d+)?$", cleaned):
        try:
            return float(cleaned), True
        except Exception:
            pass

    # Attempt JSON parsing
    try:
        val = json.loads(cleaned)
        return val, True
    except Exception:
        pass

    # Attempt Python AST / literal_eval
    try:
        val = ast.literal_eval(cleaned)
        if isinstance(val, (list, tuple, dict, set, int, float, bool)):
            return val, True
    except Exception:
        pass

    return cleaned, False


def structural_equal(
    act_val: Any,
    exp_val: Any,
    comparison_policy: str = "strict_structural",
    float_tolerance: float = 1e-5,
) -> bool:
    """
    Recursively compare two parsed values according to comparison_policy:
    - 'strict_structural': exact type and value equality.
    - 'unordered_array': arrays are compared as multisets / unordered sets.
    - 'float_tolerance': floating point numbers are compared with epsilon tolerance.
    - 'case_insensitive_string': string values are compared ignoring case.
    """
    # 1. Boolean check (must precede int check since in Python bool is subclass of int)
    if isinstance(exp_val, bool) or isinstance(act_val, bool):
        if isinstance(act_val, bool) and isinstance(exp_val, bool):
            return act_val is exp_val
        if isinstance(act_val, str) and act_val.lower() in ("true", "false"):
            return (act_val.lower() == "true") is exp_val
        if isinstance(exp_val, str) and exp_val.lower() in ("true", "false"):
            return act_val is (exp_val.lower() == "true")
        if isinstance(act_val, (int, float)) and act_val in (0, 1):
            return bool(act_val) is exp_val
        if isinstance(exp_val, (int, float)) and exp_val in (0, 1):
            return act_val is bool(exp_val)
        return False

    # 2. Number comparison
    if isinstance(exp_val, (int, float)) and isinstance(act_val, (int, float)):
        if isinstance(exp_val, int) and isinstance(act_val, int) and comparison_policy != "float_tolerance":
            return act_val == exp_val
        return math.isclose(float(act_val), float(exp_val), rel_tol=float_tolerance, abs_tol=float_tolerance)

    # 3. List / Array comparison
    if isinstance(exp_val, (list, tuple)) and isinstance(act_val, (list, tuple)):
        if len(act_val) != len(exp_val):
            return False
        if comparison_policy == "unordered_array":
            try:
                sorted_act = sorted(act_val)
                sorted_exp = sorted(exp_val)
                return all(
                    structural_equal(a, b, comparison_policy, float_tolerance)
                    for a, b in zip(sorted_act, sorted_exp)
                )
            except Exception:
                matched = [False] * len(act_val)
                for e in exp_val:
                    found = False
                    for i, a in enumerate(act_val):
                        if not matched[i] and structural_equal(a, e, comparison_policy, float_tolerance):
                            matched[i] = True
                            found = True
                            break
                    if not found:
                        return False
                return True
        else:
            return all(
                structural_equal(a, b, comparison_policy, float_tolerance)
                for a, b in zip(act_val, exp_val)
            )

    # 4. Dictionary / Map comparison
    if isinstance(exp_val, dict) and isinstance(act_val, dict):
        if set(exp_val.keys()) != set(act_val.keys()):
            return False
        return all(
            structural_equal(act_val[k], exp_val[k], comparison_policy, float_tolerance)
            for k in exp_val
        )

    # 5. String comparison
    if isinstance(exp_val, str) and isinstance(act_val, str):
        if comparison_policy == "case_insensitive_string":
            return act_val.strip().lower() == exp_val.strip().lower()
        return act_val.strip() == exp_val.strip()

    # 6. Fallback
    return str(act_val).strip() == str(exp_val).strip()


def compare_outputs(
    actual_str: str,
    expected_str: str,
    comparison_policy: str = "strict_structural",
    float_tolerance: float = 1e-5,
) -> Tuple[bool, str]:
    """
    Comprehensive, language-independent test oracle output comparison.
    Handles:
    - Exact match.
    - Full string parse.
    - Trailing return line extraction (ignoring stdout debug logs).
    - Structural array, number, boolean, object comparisons.
    - Float tolerance and unordered array policies.
    """
    act_raw = (actual_str or "").strip().replace("\r\n", "\n")
    exp_raw = (expected_str or "").strip().replace("\r\n", "\n")

    if act_raw == exp_raw:
        return True, "Exact match"

    # Parse expected output structure
    exp_val, _ = parse_output_value(exp_raw)

    # First attempt: parse full actual output
    act_val, _ = parse_output_value(act_raw)
    if structural_equal(act_val, exp_val, comparison_policy, float_tolerance):
        return True, "Structural match on full output"

    # Second attempt: If actual output has multiple lines (e.g. debug statements before return),
    # test the last non-empty line
    lines = [l.strip() for l in act_raw.split("\n") if l.strip()]
    if len(lines) > 1:
        last_val, _ = parse_output_value(lines[-1])
        if structural_equal(last_val, exp_val, comparison_policy, float_tolerance):
            return True, "Structural match on last output line"

        for l in reversed(lines[:-1]):
            candidate_val, is_s = parse_output_value(l)
            if is_s and structural_equal(candidate_val, exp_val, comparison_policy, float_tolerance):
                return True, "Structural match on emitted return line"

    # Third attempt: normalized string fallback
    norm_act = normalize_output(act_raw)
    norm_exp = normalize_output(exp_raw)
    if norm_act == norm_exp:
        return True, "Normalized string match"

    return False, f"Expected {repr(exp_raw)}, received {repr(act_raw)}"


JAVA_LEETCODE_DRIVER_SOURCE = r'''
import java.io.*;
import java.lang.reflect.*;
import java.util.*;

public class Main {
    private static String readAllInput() throws IOException {
        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            sb.append(line).append("\n");
        }
        return sb.toString().trim();
    }

    private static String stripParamLabel(String token) {
        token = token.trim();
        if (token.isEmpty()) return token;
        int eqIdx = -1;
        boolean inQuotes = false;
        for (int i = 0; i < token.length(); i++) {
            char c = token.charAt(i);
            if (c == '"' && (i == 0 || token.charAt(i - 1) != '\\')) {
                inQuotes = !inQuotes;
            }
            if (!inQuotes) {
                if (c == '[' || c == '{' || c == '(') {
                    break;
                }
                if (c == '=') {
                    eqIdx = i;
                    break;
                }
            }
        }
        if (eqIdx > 0) {
            String prefix = token.substring(0, eqIdx).trim();
            if (prefix.matches("^[a-zA-Z_$][a-zA-Z0-9_$]*$")) {
                return token.substring(eqIdx + 1).trim();
            }
        }
        return token;
    }

    private static List<String> tokenizeArguments(String raw) {
        List<String> tokens = new ArrayList<>();
        if (raw == null || raw.trim().isEmpty()) {
            return tokens;
        }

        StringBuilder current = new StringBuilder();
        int bracketDepth = 0;
        int braceDepth = 0;
        int parenDepth = 0;
        boolean inDoubleQuote = false;
        boolean inSingleQuote = false;
        boolean escaped = false;

        for (int i = 0; i < raw.length(); i++) {
            char c = raw.charAt(i);

            if (escaped) {
                current.append(c);
                escaped = false;
                continue;
            }

            if (c == '\\') {
                current.append(c);
                escaped = true;
                continue;
            }

            if (c == '"' && !inSingleQuote) {
                inDoubleQuote = !inDoubleQuote;
                current.append(c);
                continue;
            }

            if (c == '\'' && !inDoubleQuote) {
                inSingleQuote = !inSingleQuote;
                current.append(c);
                continue;
            }

            if (!inDoubleQuote && !inSingleQuote) {
                if (c == '[') bracketDepth++;
                else if (c == ']' && bracketDepth > 0) bracketDepth--;
                else if (c == '{') braceDepth++;
                else if (c == '}' && braceDepth > 0) braceDepth--;
                else if (c == '(') parenDepth++;
                else if (c == ')' && parenDepth > 0) parenDepth--;

                if (bracketDepth == 0 && braceDepth == 0 && parenDepth == 0) {
                    if (c == ',' || c == ';' || c == '\n' || c == '\r') {
                        String token = current.toString().trim();
                        if (!token.isEmpty()) {
                            tokens.add(stripParamLabel(token));
                            current.setLength(0);
                        }
                        continue;
                    }
                }
            }

            current.append(c);
        }

        String remaining = current.toString().trim();
        if (!remaining.isEmpty()) {
            tokens.add(stripParamLabel(remaining));
        }

        return tokens;
    }

    private static int[] parseIntArray(String s) {
        if (s == null) {
            throw new IllegalArgumentException("Expected integer array, but received null input.");
        }
        s = s.trim();
        if (!s.startsWith("[") || !s.endsWith("]")) {
            throw new IllegalArgumentException("Invalid integer array format: expected '[' and ']' enclosing elements, got: " + s);
        }
        String inner = s.substring(1, s.length() - 1).trim();
        if (inner.isEmpty()) {
            return new int[0];
        }

        List<String> items = new ArrayList<>();
        StringBuilder elem = new StringBuilder();
        int depth = 0;
        for (int i = 0; i < inner.length(); i++) {
            char c = inner.charAt(i);
            if (c == '[') depth++;
            else if (c == ']' && depth > 0) depth--;
            if (c == ',' && depth == 0) {
                items.add(elem.toString().trim());
                elem.setLength(0);
            } else {
                elem.append(c);
            }
        }
        String last = elem.toString().trim();
        if (!last.isEmpty()) {
            items.add(last);
        } else if (!items.isEmpty()) {
            throw new IllegalArgumentException("Invalid integer array: trailing comma or empty element in " + s);
        }

        int[] arr = new int[items.size()];
        for (int i = 0; i < items.size(); i++) {
            String item = items.get(i);
            try {
                arr[i] = Integer.parseInt(item);
            } catch (NumberFormatException e) {
                throw new IllegalArgumentException("Invalid integer in array at index " + i + ": '" + item + "' in input: " + s);
            }
        }
        return arr;
    }

    private static int[][] parseInt2DArray(String s) {
        if (s == null) {
            throw new IllegalArgumentException("Expected 2D integer array, but received null input.");
        }
        s = s.trim();
        if (!s.startsWith("[") || !s.endsWith("]")) {
            throw new IllegalArgumentException("Invalid 2D array format: expected '[' and ']', got: " + s);
        }
        String inner = s.substring(1, s.length() - 1).trim();
        if (inner.isEmpty()) {
            return new int[0][0];
        }

        List<String> subArrays = new ArrayList<>();
        StringBuilder elem = new StringBuilder();
        int depth = 0;
        for (int i = 0; i < inner.length(); i++) {
            char c = inner.charAt(i);
            if (c == '[') depth++;
            else if (c == ']' && depth > 0) depth--;
            if (c == ',' && depth == 0) {
                String sub = elem.toString().trim();
                if (!sub.isEmpty()) subArrays.add(sub);
                elem.setLength(0);
            } else {
                elem.append(c);
            }
        }
        String last = elem.toString().trim();
        if (!last.isEmpty()) subArrays.add(last);

        int[][] res = new int[subArrays.size()][];
        for (int i = 0; i < subArrays.size(); i++) {
            res[i] = parseIntArray(subArrays.get(i));
        }
        return res;
    }

    private static String[] parseStringArray(String s) {
        if (s == null) {
            throw new IllegalArgumentException("Expected string array, but received null input.");
        }
        s = s.trim();
        if (!s.startsWith("[") || !s.endsWith("]")) {
            throw new IllegalArgumentException("Invalid string array format: expected '[' and ']', got: " + s);
        }
        String inner = s.substring(1, s.length() - 1).trim();
        if (inner.isEmpty()) {
            return new String[0];
        }

        List<String> items = new ArrayList<>();
        StringBuilder elem = new StringBuilder();
        boolean inQuote = false;
        boolean escaped = false;
        for (int i = 0; i < inner.length(); i++) {
            char c = inner.charAt(i);
            if (escaped) {
                elem.append(c);
                escaped = false;
                continue;
            }
            if (c == '\\') {
                elem.append(c);
                escaped = true;
                continue;
            }
            if (c == '"') {
                inQuote = !inQuote;
                elem.append(c);
                continue;
            }
            if (c == ',' && !inQuote) {
                items.add(parseString(elem.toString().trim()));
                elem.setLength(0);
            } else {
                elem.append(c);
            }
        }
        String last = elem.toString().trim();
        if (!last.isEmpty()) {
            items.add(parseString(last));
        }

        return items.toArray(new String[0]);
    }

    private static List<Integer> parseIntList(String s) {
        int[] arr = parseIntArray(s);
        List<Integer> list = new ArrayList<>(arr.length);
        for (int v : arr) list.add(v);
        return list;
    }

    private static int parseIntVal(String s) {
        if (s == null) throw new IllegalArgumentException("Expected integer, but got null.");
        s = s.trim();
        try {
            return Integer.parseInt(s);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("Invalid integer value: '" + s + "'");
        }
    }

    private static long parseLongVal(String s) {
        if (s == null) throw new IllegalArgumentException("Expected long integer, but got null.");
        s = s.trim();
        if (s.endsWith("L") || s.endsWith("l")) s = s.substring(0, s.length() - 1);
        try {
            return Long.parseLong(s);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("Invalid long value: '" + s + "'");
        }
    }

    private static double parseDoubleVal(String s) {
        if (s == null) throw new IllegalArgumentException("Expected double, but got null.");
        s = s.trim();
        try {
            return Double.parseDouble(s);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("Invalid floating point value: '" + s + "'");
        }
    }

    private static boolean parseBooleanVal(String s) {
        if (s == null) throw new IllegalArgumentException("Expected boolean, but got null.");
        s = s.trim().toLowerCase();
        if (s.equals("true") || s.equals("1")) return true;
        if (s.equals("false") || s.equals("0")) return false;
        throw new IllegalArgumentException("Invalid boolean value: '" + s + "', expected 'true' or 'false'");
    }

    private static char parseCharVal(String s) {
        if (s == null) throw new IllegalArgumentException("Expected character, but got null.");
        s = parseString(s.trim());
        if (s.length() != 1) {
            throw new IllegalArgumentException("Invalid char value: '" + s + "', expected single character");
        }
        return s.charAt(0);
    }

    private static String parseString(String s) {
        if (s == null) return null;
        s = s.trim();
        if ((s.startsWith("\"") && s.endsWith("\"")) || (s.startsWith("'") && s.endsWith("'"))) {
            if (s.length() >= 2) {
                return s.substring(1, s.length() - 1);
            }
        }
        return s;
    }

    private static Object convertParam(String raw, Class<?> type) {
        if (raw == null) {
            if (type.isPrimitive()) {
                throw new IllegalArgumentException("Missing required primitive parameter of type " + type.getSimpleName());
            }
            return null;
        }
        if (type == int[].class) {
            return parseIntArray(raw);
        } else if (type == int[][].class) {
            return parseInt2DArray(raw);
        } else if (type == String[].class) {
            return parseStringArray(raw);
        } else if (type == List.class) {
            return parseIntList(raw);
        } else if (type == int.class || type == Integer.class) {
            return parseIntVal(raw);
        } else if (type == long.class || type == Long.class) {
            return parseLongVal(raw);
        } else if (type == double.class || type == Double.class) {
            return parseDoubleVal(raw);
        } else if (type == boolean.class || type == Boolean.class) {
            return parseBooleanVal(raw);
        } else if (type == char.class || type == Character.class) {
            return parseCharVal(raw);
        } else if (type == String.class) {
            return parseString(raw);
        }
        return raw;
    }

    private static String formatOutput(Object obj) {
        if (obj == null) return "null";
        if (obj instanceof int[]) {
            int[] arr = (int[]) obj;
            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < arr.length; i++) {
                if (i > 0) sb.append(",");
                sb.append(arr[i]);
            }
            sb.append("]");
            return sb.toString();
        } else if (obj instanceof int[][]) {
            int[][] arr = (int[][]) obj;
            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < arr.length; i++) {
                if (i > 0) sb.append(",");
                sb.append(formatOutput(arr[i]));
            }
            sb.append("]");
            return sb.toString();
        } else if (obj instanceof boolean[]) {
            return Arrays.toString((boolean[]) obj).replace(" ", "");
        } else if (obj instanceof Object[]) {
            return Arrays.deepToString((Object[]) obj).replace(" ", "");
        } else if (obj instanceof Boolean) {
            return obj.toString().toLowerCase();
        } else if (obj instanceof List) {
            StringBuilder sb = new StringBuilder("[");
            List<?> list = (List<?>) obj;
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) sb.append(",");
                sb.append(formatOutput(list.get(i)));
            }
            sb.append("]");
            return sb.toString();
        }
        return obj.toString();
    }

    public static void main(String[] args) {
        try {
            Class<?> solCls = Class.forName("Solution");
            Constructor<?> ctor = solCls.getDeclaredConstructor();
            ctor.setAccessible(true);
            Object solInst = ctor.newInstance();

            String targetName = args.length > 0 && !args[0].isEmpty() ? args[0] : null;
            Method targetMethod = null;

            if (targetName != null) {
                for (Method m : solCls.getDeclaredMethods()) {
                    if (m.getDeclaringClass() != Object.class && !Modifier.isStatic(m.getModifiers())) {
                        if (m.getName().equalsIgnoreCase(targetName)) {
                            targetMethod = m;
                            break;
                        }
                    }
                }
            }

            if (targetMethod == null) {
                for (Method m : solCls.getDeclaredMethods()) {
                    if (m.getDeclaringClass() != Object.class && !Modifier.isStatic(m.getModifiers())) {
                        targetMethod = m;
                        break;
                    }
                }
            }

            if (targetMethod == null) {
                System.err.println("Error: No solution method found on class Solution.");
                System.exit(1);
            }
            targetMethod.setAccessible(true);

            List<String> parsedArgs = tokenizeArguments(readAllInput());
            Class<?>[] paramTypes = targetMethod.getParameterTypes();

            if (parsedArgs.size() < paramTypes.length) {
                System.err.println("Error: Missing required argument(s) for method '" + targetMethod.getName() + "'. Expected " + paramTypes.length + " argument(s), but received " + parsedArgs.size() + ".");
                System.exit(1);
            }

            Object[] invokeArgs = new Object[paramTypes.length];
            for (int i = 0; i < paramTypes.length; i++) {
                invokeArgs[i] = convertParam(parsedArgs.get(i), paramTypes[i]);
            }

            Object result = targetMethod.invoke(solInst, invokeArgs);
            if (targetMethod.getReturnType() == void.class) {
                if (invokeArgs.length > 0) {
                    System.out.println(formatOutput(invokeArgs[0]));
                }
            } else {
                System.out.println(formatOutput(result));
            }
        } catch (IllegalArgumentException iae) {
            System.err.println("Validation Error: " + iae.getMessage());
            System.exit(1);
        } catch (InvocationTargetException ite) {
            Throwable cause = ite.getCause() != null ? ite.getCause() : ite;
            cause.printStackTrace(System.err);
            System.exit(1);
        } catch (Exception e) {
            System.err.println("Execution Error: " + e.getMessage());
            e.printStackTrace(System.err);
            System.exit(1);
        }
    }
}
'''


def _parse_cpp_params(param_str: str) -> List[Tuple[str, str]]:
    """Parse comma-separated C++ parameters into (type, name) pairs handling template brackets."""
    params = []
    if not param_str or not param_str.strip():
        return params
    cur = []
    depth = 0
    for c in param_str:
        if c in ("<", "(", "["):
            depth += 1
        elif c in (">", ")", "]") and depth > 0:
            depth -= 1
        if c == "," and depth == 0:
            p = "".join(cur).strip()
            if p:
                params.append(p)
            cur = []
        else:
            cur.append(c)
    last = "".join(cur).strip()
    if last:
        params.append(last)

    parsed = []
    for idx, p in enumerate(params):
        p_clean = p.replace("&", "").replace("*", "").strip()
        tokens = p_clean.split()
        if len(tokens) >= 2:
            t = " ".join(tokens[:-1])
            name = tokens[-1]
            parsed.append((t, name))
        elif len(tokens) == 1:
            parsed.append((tokens[0], f"arg_{idx}"))
    return parsed


def _build_cpp_driver(code: str, function_name: Optional[str] = None) -> str:
    """Build dynamic, type-safe C++ test-runner driver for class Solution without modifying candidate code."""
    if re.search(r"\b(int|void)\s+main\s*\(", code):
        return ""

    target_fn = function_name
    if not target_fn:
        for known in [
            "twoSum", "isValid", "lengthOfLongestSubstring", "maxSumTwoNoOverlap",
            "two_sum", "is_valid", "solve", "solution", "max_sum_two_no_overlap"
        ]:
            if re.search(rf"\b{known}\s*\(", code):
                target_fn = known
                break

    if not target_fn:
        m = re.search(r"\b(?:int|long|long\s+long|bool|double|float|string|void|vector<[^>]+>)\s+([a-zA-Z0-9_]+)\s*\(", code)
        if m and m.group(1) not in ("main", "if", "for", "while", "switch", "catch"):
            target_fn = m.group(1)

    if not target_fn:
        target_fn = "twoSum"

    # Identify return type and parameters
    fn_sig_match = re.search(rf"\b([a-zA-Z0-9_<>\s*&]+?)\s+{target_fn}\s*\(([^)]*)\)", code)
    ret_type = fn_sig_match.group(1).strip() if fn_sig_match else "auto"
    param_str = fn_sig_match.group(2).strip() if fn_sig_match else ""

    parsed_params = _parse_cpp_params(param_str)

    driver = f"""

// --- InterviewIQ Auto-Driver ---
#include <iostream>
#include <string>
#include <vector>
#include <sstream>

namespace __driver {{
    inline std::string trim(const std::string& s) {{
        size_t start = s.find_first_not_of(" \\t\\r\\n");
        if (start == std::string::npos) return "";
        size_t end = s.find_last_not_of(" \\t\\r\\n");
        return s.substr(start, end - start + 1);
    }}
    inline std::string stripEq(const std::string& l) {{
        std::string s = trim(l);
        if (s.find('=') != std::string::npos && s.front() != '[') {{
            s = s.substr(s.find('=') + 1);
            s = trim(s);
        }}
        return s;
    }}
    inline std::vector<int> parseIntArr(std::string s) {{
        s = trim(s);
        if (s.size() >= 2 && s.front() == '[' && s.back() == ']') {{
            s = s.substr(1, s.size() - 2);
        }}
        std::vector<int> res;
        if (s.empty()) return res;
        std::stringstream ss(s);
        std::string item;
        while (std::getline(ss, item, ',')) {{
            item = trim(item);
            if (!item.empty()) {{
                try {{ res.push_back(std::stoi(item)); }} catch (...) {{}}
            }}
        }}
        return res;
    }}
    inline std::string parseStr(std::string s) {{
        s = trim(s);
        if (s.size() >= 2 && ((s.front() == '"' && s.back() == '"') || (s.front() == 39 && s.back() == 39))) {{
            return s.substr(1, s.size() - 2);
        }}
        return s;
    }}
    inline std::vector<std::string> parseStrArr(std::string s) {{
        s = trim(s);
        if (s.size() >= 2 && s.front() == '[' && s.back() == ']') {{
            s = s.substr(1, s.size() - 2);
        }}
        std::vector<std::string> res;
        if (s.empty()) return res;
        std::stringstream ss(s);
        std::string item;
        while (std::getline(ss, item, ',')) {{
            item = trim(item);
            if (!item.empty()) res.push_back(parseStr(item));
        }}
        return res;
    }}
    inline void printVal(bool b) {{ std::cout << (b ? "true" : "false"); }}
    inline void printVal(int v) {{ std::cout << v; }}
    inline void printVal(long long v) {{ std::cout << v; }}
    inline void printVal(double v) {{ std::cout << v; }}
    inline void printVal(const std::string& s) {{ std::cout << s; }}
    inline void printVal(const char* s) {{ std::cout << s; }}

    template<typename T>
    void printVal(const std::vector<T>& vec) {{
        std::cout << "[";
        for (size_t i = 0; i < vec.size(); ++i) {{
            if (i > 0) std::cout << ",";
            printVal(vec[i]);
        }}
        std::cout << "]";
    }}
}}

int main() {{
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(NULL);
    Solution sol;
    std::string line;
    std::vector<std::string> lines;
    while (std::getline(std::cin, line)) {{
        std::string cleaned = __driver::stripEq(line);
        if (!cleaned.empty()) lines.push_back(cleaned);
    }}
"""

    arg_inits = []
    call_args = []
    for idx, (p_type, p_name) in enumerate(parsed_params):
        var_name = f"arg_{idx}"
        call_args.append(var_name)
        if "vector" in p_type and "string" in p_type:
            arg_inits.append(f"    std::vector<std::string> {var_name} = lines.size() > {idx} ? __driver::parseStrArr(lines[{idx}]) : std::vector<std::string>{{}};")
        elif "vector" in p_type:
            arg_inits.append(f"    std::vector<int> {var_name} = lines.size() > {idx} ? __driver::parseIntArr(lines[{idx}]) : std::vector<int>{{}};")
        elif "string" in p_type:
            arg_inits.append(f"    std::string {var_name} = lines.size() > {idx} ? __driver::parseStr(lines[{idx}]) : \"\";")
        elif "bool" in p_type:
            arg_inits.append(f"    bool {var_name} = lines.size() > {idx} ? (lines[{idx}] == \"true\" || lines[{idx}] == \"1\") : false;")
        elif "double" in p_type or "float" in p_type:
            arg_inits.append(f"    double {var_name} = lines.size() > {idx} ? std::stod(lines[{idx}]) : 0.0;")
        else:
            arg_inits.append(f"    int {var_name} = lines.size() > {idx} ? std::stoi(lines[{idx}]) : 0;")

    if not parsed_params:
        # Fallback default heuristic if parameter parsing couldn't find params
        driver += f"""
    if (!lines.empty()) {{
        if (lines[0].front() == '[') {{
            std::vector<int> arr = __driver::parseIntArr(lines[0]);
            if (lines.size() >= 2) {{
                int target = std::stoi(lines[1]);
                auto res = sol.{target_fn}(arr, target);
                __driver::printVal(res);
                std::cout << "\\n";
            }} else {{
                auto res = sol.{target_fn}(arr);
                __driver::printVal(res);
                std::cout << "\\n";
            }}
        }} else {{
            std::string s = __driver::parseStr(lines[0]);
            auto res = sol.{target_fn}(s);
            __driver::printVal(res);
            std::cout << "\\n";
        }}
    }}
    return 0;
}}
"""
    else:
        for init in arg_inits:
            driver += f"{init}\n"
        call_str = ", ".join(call_args)
        if "void" in ret_type.split():
            driver += f"""    sol.{target_fn}({call_str});\n"""
            if call_args:
                driver += f"""    __driver::printVal({call_args[0]});\n    std::cout << "\\n";\n"""
        else:
            driver += f"""    auto res = sol.{target_fn}({call_str});\n    __driver::printVal(res);\n    std::cout << "\\n";\n"""
        driver += "    return 0;\n}\n"

    return driver


def wrap_code_with_driver_if_needed(language: str, code: str, function_name: Optional[str] = None) -> str:
    """
    Wrap function-based and class-based candidate solutions with a lightweight execution driver
    so candidate code doesn't require a manual main() or stdin reader,
    while preserving standard standalone programs if already implemented.
    Never appends a duplicate main() method.
    """
    lang = language.lower().strip()

    # 1. Python LeetCode Execution Adapter
    if lang in ("python", "python3"):
        preamble = ""
        if "TreeNode" in code and "class TreeNode" not in code:
            preamble += "\nclass TreeNode:\n    def __init__(self, val=0, left=None, right=None):\n        self.val = val\n        self.left = left\n        self.right = right\n    def __repr__(self):\n        return f'TreeNode({self.val})'\n"
        if "ListNode" in code and "class ListNode" not in code:
            preamble += "\nclass ListNode:\n    def __init__(self, val=0, next=None):\n        self.val = val\n        self.next = next\n    def __repr__(self):\n        return f'ListNode({self.val})'\n"
        if any(t in code for t in ("List[", "Dict[", "Optional[", "Tuple[", "Set[")):
            preamble = "\nfrom typing import List, Dict, Optional, Tuple, Set, Any\n" + preamble

        if (
            "if __name__" in code
            or "sys.stdin" in code
            or re.search(r"^\s*def\s+main\s*\(", code, re.MULTILINE)
        ):
            return preamble + "\n" + code if preamble else code

        full_code = (preamble + "\n" + code) if preamble else code
        driver = f"""

# --- InterviewIQ Auto-Driver ---
if __name__ == '__main__':
    import sys, json, ast
    raw = sys.stdin.read().strip()
    raw_tokens = []
    if raw:
        cur, depth, in_q, q_c = [], 0, False, ''
        for c in raw:
            if c in ('"', "'") and not in_q:
                in_q, q_c = True, c
                cur.append(c)
            elif in_q and c == q_c:
                in_q, q_c = False, ''
                cur.append(c)
            elif not in_q:
                if c in ('[', '{{', '('): depth += 1
                elif c in (']', '}}', ')') and depth > 0: depth -= 1
                if depth == 0 and (c == ',' or c == ';' or c == '\\n' or c == '\\r'):
                    t = ''.join(cur).strip()
                    if t: raw_tokens.append(t)
                    cur = []
                    continue
                cur.append(c)
            else:
                cur.append(c)
        last = ''.join(cur).strip()
        if last: raw_tokens.append(last)
    lines = raw_tokens
    args = []
    for l in lines:
        if '=' in l and not l.startswith('['):
            l = l.split('=', 1)[1].strip()
        if (l.startswith('"') and l.endswith('"')) or (l.startswith("'") and l.endswith("'")):
            if len(l) >= 2:
                args.append(l[1:-1])
                continue
        try:
            args.append(json.loads(l))
        except Exception:
            if any(c in l for c in "()[]{{}}") and not (l.startswith('[') and l.endswith(']')):
                args.append(l)
            else:
                try:
                    args.append(ast.literal_eval(l))
                except Exception:
                    args.append(l)

    sol = Solution() if 'Solution' in globals() else None
    target_fn = {repr(function_name)} if {repr(function_name)} else None
    fn = getattr(sol, target_fn, None) if sol and target_fn else (globals().get(target_fn) if target_fn else None)
    if not fn and sol:
        methods = [m for m in dir(sol) if not m.startswith('_')]
        if target_fn:
            for m in methods:
                if m.lower() == target_fn.lower():
                    fn = getattr(sol, m)
                    break
        if not fn and methods:
            fn = getattr(sol, methods[0])
    if not fn:
        for candidate in ['twoSum', 'two_sum', 'isValid', 'is_valid', 'lengthOfLongestSubstring', 'solve', 'solution']:
            if candidate in globals() and callable(globals()[candidate]):
                fn = globals()[candidate]
                break

    if fn:
        res = fn(*args)
        if res is not None:
            if isinstance(res, bool):
                print(str(res).lower())
            else:
                try:
                    print(json.dumps(res, separators=(',', ':')))
                except Exception:
                    print(res)
        elif args:
            print(json.dumps(args[0], separators=(',', ':')))
"""
        return full_code + driver

    # 2. JavaScript / TypeScript LeetCode Execution Adapter
    elif lang in ("javascript", "typescript", "js", "ts"):
        if "readFileSync" in code or ("console.log" in code and "function" not in code and "class" not in code):
            return code

        driver = f"""

// --- InterviewIQ Auto-Driver ---
if (typeof require !== 'undefined') {{
    try {{
        const fs = require('fs');
        const raw = fs.readFileSync(0, 'utf-8').trim();
        if (raw) {{
            const lines = raw.split('\\n').map(l => l.trim()).filter(Boolean);
            const args = lines.map(l => {{
                if (l.includes('=') && !l.startsWith('[')) {{
                    l = l.split('=').slice(1).join('=').trim();
                }}
                if ((l.startsWith('"') && l.endsWith('"')) || (l.startsWith("'") && l.endsWith("'"))) {{
                    if (l.length >= 2) return l.slice(1, -1);
                }}
                try {{ return JSON.parse(l); }} catch (e) {{ return l; }}
            }});

            let fn = null;
            const targetName = {repr(function_name)} || null;
            const solInst = typeof Solution !== 'undefined' ? new Solution() : null;

            if (solInst && targetName && typeof solInst[targetName] === 'function') {{
                fn = solInst[targetName].bind(solInst);
            }} else if (targetName && typeof globalThis[targetName] === 'function') {{
                fn = globalThis[targetName];
            }} else if (solInst) {{
                const methods = Object.getOwnPropertyNames(Object.getPrototypeOf(solInst)).filter(m => m !== 'constructor');
                if (methods.length > 0) fn = solInst[methods[0]].bind(solInst);
            }}

            if (!fn) {{
                for (const candidate of ['twoSum', 'two_sum', 'isValid', 'is_valid', 'lengthOfLongestSubstring', 'solve', 'solution']) {{
                    if (typeof globalThis[candidate] === 'function') {{
                        fn = globalThis[candidate];
                        break;
                    }}
                }}
            }}

            if (fn) {{
                const res = fn(...args);
                if (res !== undefined) {{
                    if (typeof res === 'boolean') {{
                        console.log(res ? 'true' : 'false');
                    }} else {{
                        console.log(JSON.stringify(res));
                    }}
                }} else if (args.length > 0) {{
                    console.log(JSON.stringify(args[0]));
                }}
            }}
        }}
    }} catch (err) {{
        console.error(err);
    }}
}}
"""
        return code + driver

    # 3. C++ LeetCode Execution Adapter
    elif lang in ("cpp", "c++"):
        cpp_driver = _build_cpp_driver(code, function_name)
        if cpp_driver:
            return code + cpp_driver
        return code

    # 4. Java fallback for single-file runners (Piston)
    elif lang in ("java",):
        has_main = bool(re.search(r"\b(public\s+)?static\s+void\s+main\s*\(", code))
        if has_main:
            return code
        # For combined execution, ensure class Solution is not public so Main can be the public class
        modified_sol = re.sub(r"\bpublic\s+class\s+Solution\b", "class Solution", code)
        return modified_sol + "\n" + JAVA_LEETCODE_DRIVER_SOURCE

    return code


def execute_code_locally(
    language: str,
    code: str,
    stdin: str = "",
    timeout_sec: float = 8.0,
    function_name: Optional[str] = None,
) -> Optional[CodeExecutionResponse]:
    """
    Execute code using locally installed toolchains (Python, Node.js, MinGW GCC/G++, Oracle Java).
    Provides instant, deterministic sandboxed subprocess execution with resource caps and timeouts.
    """
    lang = language.lower().strip()
    executable_code = wrap_code_with_driver_if_needed(language, code, function_name)
    start_time = time.time()

    # 1. Python execution via sys.executable
    if lang in ("python", "python3"):
        if not PYTHON_BIN:
            return None
        try:
            res = subprocess.run(
                [PYTHON_BIN, "-c", executable_code],
                input=stdin,
                text=True,
                capture_output=True,
                timeout=timeout_sec,
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            stdout = res.stdout
            stderr = res.stderr
            exit_code = res.returncode
            if exit_code != 0:
                is_comp = "SyntaxError" in stderr or "IndentationError" in stderr
                status = "compilation_error" if is_comp else "runtime_error"
                return CodeExecutionResponse(
                    stdout=stdout,
                    stderr=stderr,
                    output=stderr or stdout,
                    exit_code=exit_code,
                    execution_time_ms=elapsed_ms,
                    status=status,
                    error=stderr.strip() or f"Process exited with code {exit_code}",
                )
            return CodeExecutionResponse(
                stdout=stdout,
                stderr=stderr,
                output=stdout or stderr,
                exit_code=0,
                execution_time_ms=elapsed_ms,
                status="success",
                error=None,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return CodeExecutionResponse(
                stdout="",
                stderr="Execution timed out.",
                output="Execution timed out.",
                exit_code=124,
                execution_time_ms=elapsed_ms,
                status="timeout",
                error=f"Execution timed out after {timeout_sec} seconds.",
            )
        except Exception as exc:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return CodeExecutionResponse(
                status="error",
                error=f"Local Python execution error: {type(exc).__name__}: {str(exc)}",
                stderr=str(exc),
                exit_code=1,
                execution_time_ms=elapsed_ms,
            )

    # 2. JavaScript / TypeScript execution via Node.js
    elif lang in ("javascript", "typescript", "js", "ts"):
        if not NODE_BIN or not os.path.exists(NODE_BIN):
            return None
        try:
            res = subprocess.run(
                [NODE_BIN, "-e", executable_code],
                input=stdin,
                text=True,
                capture_output=True,
                timeout=timeout_sec,
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            stdout = res.stdout
            stderr = res.stderr
            exit_code = res.returncode
            if exit_code != 0:
                is_comp = "SyntaxError" in stderr
                status = "compilation_error" if is_comp else "runtime_error"
                return CodeExecutionResponse(
                    stdout=stdout,
                    stderr=stderr,
                    output=stderr or stdout,
                    exit_code=exit_code,
                    execution_time_ms=elapsed_ms,
                    status=status,
                    error=stderr.strip() or f"Process exited with code {exit_code}",
                )
            return CodeExecutionResponse(
                stdout=stdout,
                stderr=stderr,
                output=stdout or stderr,
                exit_code=0,
                execution_time_ms=elapsed_ms,
                status="success",
                error=None,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return CodeExecutionResponse(
                stdout="",
                stderr="Execution timed out.",
                output="Execution timed out.",
                exit_code=124,
                execution_time_ms=elapsed_ms,
                status="timeout",
                error=f"Execution timed out after {timeout_sec} seconds.",
            )
        except Exception as exc:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return CodeExecutionResponse(
                status="error",
                error=f"Local Node.js execution error: {type(exc).__name__}: {str(exc)}",
                stderr=str(exc),
                exit_code=1,
                execution_time_ms=elapsed_ms,
            )

    # 3. C++ execution via MinGW g++
    elif lang in ("cpp", "c++"):
        if not GPP_BIN or not os.path.exists(GPP_BIN):
            return None
        try:
            with tempfile.TemporaryDirectory(dir=BUILD_CACHE_DIR) as td:
                src_path = os.path.join(td, "solution.cpp")
                exe_path = os.path.join(td, "solution.exe" if os.name == "nt" else "solution")
                with open(src_path, "w", encoding="utf-8") as f:
                    f.write(executable_code)
                comp = subprocess.run(
                    [GPP_BIN, src_path, "-o", exe_path, "-O2", "-std=c++17"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if comp.returncode != 0:
                    elapsed_ms = round((time.time() - start_time) * 1000, 2)
                    return CodeExecutionResponse(
                        stdout="",
                        stderr=comp.stderr,
                        output=comp.stderr,
                        exit_code=comp.returncode,
                        execution_time_ms=elapsed_ms,
                        status="compilation_error",
                        error=comp.stderr.strip() or "C++ compilation failed.",
                    )
                run_res = subprocess.run(
                    [exe_path],
                    input=stdin,
                    text=True,
                    capture_output=True,
                    timeout=timeout_sec,
                )
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                if run_res.returncode != 0:
                    return CodeExecutionResponse(
                        stdout=run_res.stdout,
                        stderr=run_res.stderr,
                        output=run_res.stderr or run_res.stdout,
                        exit_code=run_res.returncode,
                        execution_time_ms=elapsed_ms,
                        status="runtime_error",
                        error=run_res.stderr.strip() or f"Process exited with code {run_res.returncode}",
                    )
                return CodeExecutionResponse(
                    stdout=run_res.stdout,
                    stderr=run_res.stderr,
                    output=run_res.stdout or run_res.stderr,
                    exit_code=0,
                    execution_time_ms=elapsed_ms,
                    status="success",
                    error=None,
                )
        except subprocess.TimeoutExpired:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return CodeExecutionResponse(
                stdout="",
                stderr="Execution timed out.",
                output="Execution timed out.",
                exit_code=124,
                execution_time_ms=elapsed_ms,
                status="timeout",
                error=f"Execution timed out after {timeout_sec} seconds.",
            )
        except Exception as exc:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return CodeExecutionResponse(
                status="error",
                error=f"Local C++ execution error: {type(exc).__name__}: {str(exc)}",
                stderr=str(exc),
                exit_code=1,
                execution_time_ms=elapsed_ms,
            )

    # 4. C execution via MinGW gcc
    elif lang in ("c",):
        if not GCC_BIN or not os.path.exists(GCC_BIN):
            return None
        try:
            with tempfile.TemporaryDirectory(dir=BUILD_CACHE_DIR) as td:
                src_path = os.path.join(td, "solution.c")
                exe_path = os.path.join(td, "solution.exe" if os.name == "nt" else "solution")
                with open(src_path, "w", encoding="utf-8") as f:
                    f.write(executable_code)
                comp = subprocess.run(
                    [GCC_BIN, src_path, "-o", exe_path, "-O2"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if comp.returncode != 0:
                    elapsed_ms = round((time.time() - start_time) * 1000, 2)
                    return CodeExecutionResponse(
                        stdout="",
                        stderr=comp.stderr,
                        output=comp.stderr,
                        exit_code=comp.returncode,
                        execution_time_ms=elapsed_ms,
                        status="compilation_error",
                        error=comp.stderr.strip() or "C compilation failed.",
                    )
                run_res = subprocess.run(
                    [exe_path],
                    input=stdin,
                    text=True,
                    capture_output=True,
                    timeout=timeout_sec,
                )
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                if run_res.returncode != 0:
                    return CodeExecutionResponse(
                        stdout=run_res.stdout,
                        stderr=run_res.stderr,
                        output=run_res.stderr or run_res.stdout,
                        exit_code=run_res.returncode,
                        execution_time_ms=elapsed_ms,
                        status="runtime_error",
                        error=run_res.stderr.strip() or f"Process exited with code {run_res.returncode}",
                    )
                return CodeExecutionResponse(
                    stdout=run_res.stdout,
                    stderr=run_res.stderr,
                    output=run_res.stdout or run_res.stderr,
                    exit_code=0,
                    execution_time_ms=elapsed_ms,
                    status="success",
                    error=None,
                )
        except subprocess.TimeoutExpired:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return CodeExecutionResponse(
                stdout="",
                stderr="Execution timed out.",
                output="Execution timed out.",
                exit_code=124,
                execution_time_ms=elapsed_ms,
                status="timeout",
                error=f"Execution timed out after {timeout_sec} seconds.",
            )
        except Exception as exc:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return CodeExecutionResponse(
                status="error",
                error=f"Local C execution error: {type(exc).__name__}: {str(exc)}",
                stderr=str(exc),
                exit_code=1,
                execution_time_ms=elapsed_ms,
            )

    # 5. Java execution via javac + java
    elif lang in ("java",):
        if not JAVAC_BIN or not JAVA_BIN or not os.path.exists(JAVAC_BIN) or not os.path.exists(JAVA_BIN):
            return None
        try:
            has_main = bool(re.search(r"\b(public\s+)?static\s+void\s+main\s*\(", code))
            with tempfile.TemporaryDirectory(dir=BUILD_CACHE_DIR) as td:
                if has_main:
                    match = re.search(r"\bclass\s+([A-Za-z0-9_]+)", code)
                    class_name = match.group(1) if match else "Main"
                    src_path = os.path.join(td, f"{class_name}.java")
                    with open(src_path, "w", encoding="utf-8") as f:
                        f.write(code)
                    comp = subprocess.run(
                        [JAVAC_BIN, src_path],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    run_class = class_name
                    run_args = [JAVA_BIN, "-cp", td, run_class]
                else:
                    # LeetCode-style class Solution
                    sol_path = os.path.join(td, "Solution.java")
                    main_path = os.path.join(td, "Main.java")
                    sol_code = code
                    if "import java.util." not in sol_code:
                        sol_code = "import java.util.*;\nimport java.io.*;\n" + sol_code
                    with open(sol_path, "w", encoding="utf-8") as f:
                        f.write(sol_code)
                    with open(main_path, "w", encoding="utf-8") as f:
                        f.write(JAVA_LEETCODE_DRIVER_SOURCE)
                    comp = subprocess.run(
                        [JAVAC_BIN, sol_path, main_path],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    run_args = [JAVA_BIN, "-cp", td, "Main", function_name or ""]

                if comp.returncode != 0:
                    elapsed_ms = round((time.time() - start_time) * 1000, 2)
                    return CodeExecutionResponse(
                        stdout="",
                        stderr=comp.stderr,
                        output=comp.stderr,
                        exit_code=comp.returncode,
                        execution_time_ms=elapsed_ms,
                        status="compilation_error",
                        error=comp.stderr.strip() or "Java compilation failed.",
                    )
                run_res = subprocess.run(
                    run_args,
                    input=stdin,
                    text=True,
                    capture_output=True,
                    timeout=timeout_sec,
                )
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                if run_res.returncode != 0:
                    return CodeExecutionResponse(
                        stdout=run_res.stdout,
                        stderr=run_res.stderr,
                        output=run_res.stderr or run_res.stdout,
                        exit_code=run_res.returncode,
                        execution_time_ms=elapsed_ms,
                        status="runtime_error",
                        error=run_res.stderr.strip() or f"Process exited with code {run_res.returncode}",
                    )
                return CodeExecutionResponse(
                    stdout=run_res.stdout,
                    stderr=run_res.stderr,
                    output=run_res.stdout or run_res.stderr,
                    exit_code=0,
                    execution_time_ms=elapsed_ms,
                    status="success",
                    error=None,
                )
        except subprocess.TimeoutExpired:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return CodeExecutionResponse(
                stdout="",
                stderr="Execution timed out.",
                output="Execution timed out.",
                exit_code=124,
                execution_time_ms=elapsed_ms,
                status="timeout",
                error=f"Execution timed out after {timeout_sec} seconds.",
            )
        except Exception as exc:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return CodeExecutionResponse(
                status="error",
                error=f"Local Java execution error: {type(exc).__name__}: {str(exc)}",
                stderr=str(exc),
                exit_code=1,
                execution_time_ms=elapsed_ms,
            )

    return None


def get_configured_piston_url() -> Optional[str]:
    """
    Get configured Piston URL.
    Safely rejects un-whitelisted default emkc.org public endpoint unless an explicit API key is set.
    """
    url = getattr(settings, "PISTON_API_URL", None) or os.environ.get("PISTON_API_URL")
    if not url:
        return None
    url = url.strip()
    api_key = getattr(settings, "PISTON_API_KEY", None) or os.environ.get("PISTON_API_KEY")
    # If URL is still the legacy public endpoint and no key is configured, treat as unconfigured
    if "emkc.org" in url and not api_key:
        return None
    return url


def get_configured_judge0_url() -> Optional[str]:
    """
    Get configured Judge0 submissions URL.
    Returns RapidAPI endpoint if JUDGE0_API_KEY is configured, or custom self-hosted endpoint.
    """
    custom_url = getattr(settings, "JUDGE0_API_URL", None) or os.environ.get("JUDGE0_API_URL")
    if custom_url and custom_url.strip():
        return custom_url.strip()
    api_key = getattr(settings, "JUDGE0_API_KEY", None) or os.environ.get("JUDGE0_API_KEY")
    if api_key and api_key.strip():
        return "https://judge0-ce.p.rapidapi.com/submissions?wait=true&base64_encoded=false"
    return None


def execute_code_via_piston(
    language: str,
    executable_code: str,
    stdin: str,
    timeout_sec: float,
    config: Dict[str, Any],
    piston_url: str,
    piston_api_key: Optional[str] = None,
) -> CodeExecutionResponse:
    """Execute code using a Piston-compatible instance (self-hosted or hosted with API key)."""
    lang_key = language.lower().strip()
    if lang_key == "java" and not re.search(r"\b(public\s+)?static\s+void\s+main\s*\(", executable_code):
        files_payload = [
            {"name": "Solution.java", "content": executable_code},
            {"name": "Main.java", "content": JAVA_LEETCODE_DRIVER_SOURCE},
        ]
    else:
        files_payload = [
            {
                "name": config["file_name"],
                "content": executable_code,
            }
        ]

    payload = {
        "language": config["piston_lang"],
        "version": config["version"],
        "files": files_payload,
        "stdin": stdin,
        "run_timeout": int(timeout_sec * 1000),
        "compile_timeout": 10000,
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "InterviewIQ-ExecutionEngine/2.0",
    }
    if piston_api_key:
        headers["Authorization"] = piston_api_key
        headers["x-api-key"] = piston_api_key

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(piston_url, data=req_data, headers=headers)

    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec + 6.0) as resp:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            result_data = json.loads(resp.read().decode("utf-8"))

        run_info = result_data.get("run", {})
        compile_info = result_data.get("compile", {})

        compile_stderr = compile_info.get("stderr", "")
        if compile_info.get("code", 0) != 0 and compile_stderr:
            return CodeExecutionResponse(
                stdout="",
                stderr=compile_stderr,
                output=compile_stderr,
                exit_code=compile_info.get("code", 1),
                execution_time_ms=elapsed_ms,
                status="compilation_error",
                error=compile_stderr,
                provider="piston",
            )

        stdout = run_info.get("stdout", "")
        stderr = run_info.get("stderr", "")
        output = run_info.get("output", stdout or stderr)
        exit_code = run_info.get("code", 0)
        signal = run_info.get("signal")

        if signal == "SIGKILL" or "timed out" in stderr.lower():
            status = "timeout"
            err_msg = f"Execution timed out after {timeout_sec} seconds."
        elif exit_code != 0:
            status = "runtime_error"
            err_msg = stderr or f"Process exited with code {exit_code}"
        else:
            status = "success"
            err_msg = None

        return CodeExecutionResponse(
            stdout=stdout,
            stderr=stderr,
            output=output,
            exit_code=exit_code,
            execution_time_ms=elapsed_ms,
            status=status,
            error=err_msg,
            provider="piston",
        )

    except urllib.error.HTTPError as exc:
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        try:
            err_body = exc.read().decode("utf-8")
            err_json = json.loads(err_body)
            msg = err_json.get("message", f"HTTP {exc.code}: {exc.reason}")
        except Exception:
            msg = f"HTTP {exc.code}: {exc.reason}"

        return CodeExecutionResponse(
            status="error",
            error=f"Piston provider error ({exc.code}): {msg}",
            stderr=f"Piston provider error ({exc.code}): {msg}",
            exit_code=1,
            execution_time_ms=elapsed_ms,
            provider="piston",
        )

    except urllib.error.URLError as exc:
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return CodeExecutionResponse(
            status="error",
            error=f"Piston provider unavailable: {exc.reason}",
            stderr=f"Piston provider unavailable: {exc.reason}",
            exit_code=1,
            execution_time_ms=elapsed_ms,
            provider="piston",
        )

    except Exception as exc:
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return CodeExecutionResponse(
            status="error",
            error=f"Piston execution error: {type(exc).__name__}: {str(exc)}",
            stderr=str(exc),
            exit_code=1,
            execution_time_ms=elapsed_ms,
            provider="piston",
        )


def execute_code_via_judge0(
    language: str,
    executable_code: str,
    stdin: str,
    timeout_sec: float,
    judge0_url: str,
    judge0_api_key: Optional[str] = None,
    judge0_host: Optional[str] = "judge0-ce.p.rapidapi.com",
) -> CodeExecutionResponse:
    """Execute code using Judge0 CE API (RapidAPI or self-hosted instance)."""
    lang_key = language.lower().strip()
    judge0_lang_id = JUDGE0_LANGUAGE_IDS.get(lang_key)
    if not judge0_lang_id:
        return CodeExecutionResponse(
            status="error",
            error=f"Language '{language}' does not have a mapped Judge0 runtime ID.",
            exit_code=1,
            provider="judge0",
        )

    payload = {
        "source_code": executable_code,
        "language_id": judge0_lang_id,
        "stdin": stdin,
        "cpu_time_limit": min(timeout_sec, 15.0),
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "InterviewIQ-ExecutionEngine/2.0",
    }
    if judge0_api_key:
        headers["X-RapidAPI-Key"] = judge0_api_key
        headers["X-RapidAPI-Host"] = judge0_host or "judge0-ce.p.rapidapi.com"
        headers["X-Auth-Token"] = judge0_api_key

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(judge0_url, data=req_data, headers=headers)

    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec + 8.0) as resp:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            result_data = json.loads(resp.read().decode("utf-8"))

        status_obj = result_data.get("status", {})
        status_id = status_obj.get("id", 0)
        stdout = result_data.get("stdout") or ""
        stderr = result_data.get("stderr") or ""
        compile_output = result_data.get("compile_output") or ""
        time_taken = result_data.get("time")
        exec_time_ms = round(float(time_taken) * 1000, 2) if time_taken else elapsed_ms

        if status_id == 6 or compile_output:
            return CodeExecutionResponse(
                stdout="",
                stderr=compile_output,
                output=compile_output,
                exit_code=1,
                execution_time_ms=exec_time_ms,
                status="compilation_error",
                error=compile_output.strip() or "Compilation failed.",
                provider="judge0",
            )
        elif status_id == 5 or "time limit exceeded" in (status_obj.get("description") or "").lower():
            return CodeExecutionResponse(
                stdout=stdout,
                stderr="Execution timed out.",
                output="Execution timed out.",
                exit_code=124,
                execution_time_ms=exec_time_ms,
                status="timeout",
                error=f"Execution timed out after {timeout_sec} seconds.",
                provider="judge0",
            )
        elif status_id in (7, 8, 9, 10, 11, 12) or (stderr and status_id not in (3, 4)):
            return CodeExecutionResponse(
                stdout=stdout,
                stderr=stderr,
                output=stderr or stdout,
                exit_code=1,
                execution_time_ms=exec_time_ms,
                status="runtime_error",
                error=stderr.strip() or status_obj.get("description", "Runtime error"),
                provider="judge0",
            )
        elif status_id in (3, 4):
            # Status 3 (Accepted) or 4 (Wrong Answer) - output comparison logic handles pass/fail
            return CodeExecutionResponse(
                stdout=stdout,
                stderr=stderr,
                output=stdout or stderr,
                exit_code=0,
                execution_time_ms=exec_time_ms,
                status="success",
                error=None,
                provider="judge0",
            )
        else:
            return CodeExecutionResponse(
                status="error",
                error=f"Judge0 provider status {status_id}: {status_obj.get('description', 'Unknown status')}",
                stderr=stderr or compile_output,
                exit_code=1,
                execution_time_ms=exec_time_ms,
                provider="judge0",
            )

    except urllib.error.HTTPError as exc:
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        try:
            err_body = exc.read().decode("utf-8")
            err_json = json.loads(err_body)
            msg = err_json.get("message", f"HTTP {exc.code}: {exc.reason}")
        except Exception:
            msg = f"HTTP {exc.code}: {exc.reason}"

        return CodeExecutionResponse(
            status="error",
            error=f"Judge0 provider error ({exc.code}): {msg}",
            stderr=f"Judge0 provider error ({exc.code}): {msg}",
            exit_code=1,
            execution_time_ms=elapsed_ms,
            provider="judge0",
        )

    except urllib.error.URLError as exc:
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return CodeExecutionResponse(
            status="error",
            error=f"Judge0 provider unavailable: {exc.reason}",
            stderr=f"Judge0 provider unavailable: {exc.reason}",
            exit_code=1,
            execution_time_ms=elapsed_ms,
            provider="judge0",
        )

    except Exception as exc:
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return CodeExecutionResponse(
            status="error",
            error=f"Judge0 execution error: {type(exc).__name__}: {str(exc)}",
            stderr=str(exc),
            exit_code=1,
            execution_time_ms=elapsed_ms,
            provider="judge0",
        )


async def execute_code_sandboxed(
    language: str,
    code: str,
    stdin: str = "",
    timeout_sec: float = 8.0,
    function_name: Optional[str] = None,
) -> CodeExecutionResponse:
    """
    Execute code in a sandboxed runtime.
    Execution hierarchy:
    1. Local isolated subprocess runner (instant, deterministic for Python, JavaScript, C++, C, Java).
    2. Configured Piston runner (self-hosted or hosted with valid API key).
    3. Configured Judge0 runner (RapidAPI or self-hosted).
    4. Honest diagnostic provider error detailing required environment variables.
    """
    lang_key = language.lower().strip()
    config = LANGUAGE_CONFIGS.get(lang_key)

    if not config:
        return CodeExecutionResponse(
            status="error",
            error=f"Language '{language}' is not supported. Supported: {list(LANGUAGE_CONFIGS.keys())}",
            stderr=f"Language '{language}' is not supported.",
            exit_code=1,
        )

    # 1. Attempt local execution runner first
    local_res = execute_code_locally(language, code, stdin=stdin, timeout_sec=timeout_sec, function_name=function_name)
    if local_res is not None:
        local_res.provider = "local"
        return local_res

    executable_code = wrap_code_with_driver_if_needed(language, code, function_name)

    # 2. Check for configured Piston provider
    piston_url = get_configured_piston_url()
    piston_api_key = getattr(settings, "PISTON_API_KEY", None) or os.environ.get("PISTON_API_KEY")
    if piston_url:
        return execute_code_via_piston(
            language=language,
            executable_code=executable_code,
            stdin=stdin,
            timeout_sec=timeout_sec,
            config=config,
            piston_url=piston_url,
            piston_api_key=piston_api_key,
        )

    # 3. Check for configured Judge0 provider
    judge0_url = get_configured_judge0_url()
    judge0_api_key = getattr(settings, "JUDGE0_API_KEY", None) or os.environ.get("JUDGE0_API_KEY")
    judge0_host = getattr(settings, "JUDGE0_HOST", "judge0-ce.p.rapidapi.com") or os.environ.get("JUDGE0_HOST", "judge0-ce.p.rapidapi.com")
    if judge0_url and judge0_api_key:
        return execute_code_via_judge0(
            language=language,
            executable_code=executable_code,
            stdin=stdin,
            timeout_sec=timeout_sec,
            judge0_url=judge0_url,
            judge0_api_key=judge0_api_key,
            judge0_host=judge0_host,
        )

    # 4. Informative diagnostic state when no remote provider is configured
    local_available = []
    if PYTHON_BIN:
        local_available.append("Python 3")
    if NODE_BIN:
        local_available.append("JavaScript/TypeScript")
    if GPP_BIN:
        local_available.append("C++")
    if GCC_BIN:
        local_available.append("C")
    if JAVAC_BIN and JAVA_BIN:
        local_available.append("Java")
    local_available.append("SQL")
    local_summary = ", ".join(local_available)

    return CodeExecutionResponse(
        status="error",
        error=(
            f"Execution provider not configured: The public Piston API (emkc.org) is restricted "
            f"(whitelist-only as of 2/15/2026). To execute '{language}', please configure a remote execution provider "
            f"in backend/.env by setting PISTON_API_URL (and optional PISTON_API_KEY for self-hosted/hosted Piston) "
            f"or JUDGE0_API_KEY (and optional JUDGE0_API_URL for Judge0 CE). "
            f"Locally operational languages on this server: {local_summary}."
        ),
        stderr=f"Execution provider unavailable for '{language}'.",
        exit_code=1,
        execution_time_ms=0.0,
    )


async def evaluate_code_against_test_cases(
    question_id: str,
    language: str,
    code: str,
    test_cases: List[TestCase],
    function_name: Optional[str] = None,
    comparison_policy: Optional[str] = "strict_structural",
    float_tolerance: Optional[float] = 1e-5,
) -> CodeSubmissionResult:
    """
    Run candidate code sequentially against all test cases for a question.
    Uses language-independent structural output comparison engine.
    Ensures hidden test inputs and expected outputs are never leaked to candidate.
    Distinguishes compilation, runtime, and execution provider errors.
    Never marks a solution as accepted if execution failed.
    """
    if not test_cases:
        # Honest state: test cases not configured on question definition
        return CodeSubmissionResult(
            question_id=question_id,
            language=language,
            total_tests=0,
            passed_tests=0,
            all_passed=False,
            results=[],
            status="no_test_cases_configured",
            compilation_error="Test cases are not configured on this question definition. Use Custom Input (stdin) to test your solution.",
        )

    results: List[TestCaseResult] = []
    passed_count = 0
    compilation_error: Optional[str] = None
    provider_error: Optional[str] = None

    for tc in test_cases:
        exec_res = await execute_code_sandboxed(
            language,
            code,
            stdin=tc.input,
            function_name=function_name,
        )

        # Distinguish upstream execution provider errors (do not misattribute to candidate code)
        if exec_res.status == "error":
            provider_error = exec_res.error or "Execution provider unavailable."
            results.append(
                TestCaseResult(
                    test_case_id=tc.id,
                    input=tc.input if not tc.is_hidden else "[Hidden Test Case]",
                    expected_output=tc.expected_output if not tc.is_hidden else "[Hidden Expected Output]",
                    actual_output=f"[Execution Provider Error: {provider_error}]",
                    passed=False,
                    is_hidden=tc.is_hidden,
                    execution_time_ms=exec_res.execution_time_ms,
                    error=provider_error,
                    comparison_policy=comparison_policy,
                )
            )
            # Abort subsequent runs on provider failure
            break

        if exec_res.status == "compilation_error":
            compilation_error = exec_res.stderr or exec_res.error or exec_res.output
            results.append(
                TestCaseResult(
                    test_case_id=tc.id,
                    input=tc.input if not tc.is_hidden else "[Hidden Test Case]",
                    expected_output=tc.expected_output if not tc.is_hidden else "[Hidden Expected Output]",
                    actual_output=exec_res.output or exec_res.stderr or "[Compilation Error]",
                    passed=False,
                    is_hidden=tc.is_hidden,
                    execution_time_ms=exec_res.execution_time_ms,
                    error=compilation_error,
                    comparison_policy=comparison_policy,
                )
            )
            # Abort subsequent runs on compilation failure
            break

        # Determine effective comparison policy and tolerance for this test case
        tc_policy = getattr(tc, "comparison_policy", None) or comparison_policy or "strict_structural"
        tc_tolerance = getattr(tc, "float_tolerance", None) or float_tolerance or 1e-5

        matched_output, diag = compare_outputs(
            actual_str=exec_res.stdout or "",
            expected_str=tc.expected_output,
            comparison_policy=tc_policy,
            float_tolerance=tc_tolerance,
        )

        passed = (
            matched_output
            and exec_res.exit_code == 0
            and exec_res.status == "success"
        )

        if passed:
            passed_count += 1

        actual_output_display = (
            exec_res.stdout.strip()
            if exec_res.stdout
            else (exec_res.stderr.strip() or exec_res.output.strip() or exec_res.error or "")
        )

        # Enforce strict hidden test protection
        case_input_display = tc.input if not tc.is_hidden else "[Hidden Test Case Input]"
        case_expected_display = tc.expected_output if not tc.is_hidden else "[Hidden Expected Output]"
        case_actual_display = actual_output_display if not tc.is_hidden else ("[Passed]" if passed else "[Output Mismatch]")
        case_error_display = (exec_res.error or (None if passed else diag)) if not tc.is_hidden else (None if passed else "[Hidden Test Failed]")

        results.append(
            TestCaseResult(
                test_case_id=tc.id,
                input=case_input_display,
                expected_output=case_expected_display,
                actual_output=case_actual_display,
                passed=passed,
                is_hidden=tc.is_hidden,
                execution_time_ms=exec_res.execution_time_ms,
                error=case_error_display,
                comparison_policy=tc_policy,
            )
        )

    all_passed = (
        passed_count == len(test_cases)
        and compilation_error is None
        and provider_error is None
    )

    final_status = "evaluated"
    if provider_error:
        final_status = "provider_error"
    elif compilation_error:
        final_status = "compilation_error"

    return CodeSubmissionResult(
        question_id=question_id,
        language=language,
        total_tests=len(test_cases),
        passed_tests=passed_count,
        all_passed=all_passed,
        results=results,
        status=final_status,
        compilation_error=compilation_error,
        provider_error=provider_error,
    )
