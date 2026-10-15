"""
Deterministic Skill Normalization & Alias Mapping Service.

Provides conservative, canonical normalization for skill names without
collapsing distinct technologies or creating false-positive substring matches.
"""
import re
from typing import Dict, Iterable, Optional, Set, Tuple

# Conservative Canonical Alias Mapping:
# Key: normalized lookup key (lowercase, stripped of punctuation)
# Value: Canonical display name
CANONICAL_SKILL_MAP: Dict[str, str] = {
    # Relational & SQL Databases
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "mariadb": "MariaDB",
    "oracle": "Oracle DB",
    "sql server": "MS SQL Server",
    "mssql": "MS SQL Server",
    "sql": "SQL",
    "psql": "psql",

    # NoSQL & Caching
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "redis": "Redis",
    "cassandra": "Cassandra",
    "dynamodb": "DynamoDB",
    "elasticsearch": "Elasticsearch",

    # Core Languages
    "python": "Python",
    "python3": "Python",
    "python 3": "Python",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "golang": "Go",
    "go": "Go",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "c": "C",
    "rust": "Rust",
    "ruby": "Ruby",
    "php": "PHP",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "scala": "Scala",

    # Frontend Frameworks & Libraries
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "vue": "Vue.js",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    "svelte": "Svelte",
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",

    # Backend Frameworks
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "node": "Node.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "express": "Express.js",
    "express.js": "Express.js",
    "expressjs": "Express.js",
    "spring": "Spring Boot",
    "spring boot": "Spring Boot",
    "nestjs": "NestJS",

    # Cloud & DevOps
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "azure": "Azure",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "jenkins": "Jenkins",
    "github actions": "GitHub Actions",

    # Version Control & Collaboration
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",

    # APIs & Messaging
    "rest": "REST APIs",
    "rest api": "REST APIs",
    "restful": "REST APIs",
    "restful api": "REST APIs",
    "restful apis": "REST APIs",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "websockets": "WebSockets",
    "websocket": "WebSockets",
    "kafka": "Apache Kafka",
    "rabbitmq": "RabbitMQ",
}

# Explicit pairs that must NEVER collide or match
DISALLOWED_COLLISIONS: Set[Tuple[str, str]] = {
    ("java", "javascript"),
    ("c", "c++"),
    ("c", "c#"),
    ("c", "css"),
    ("go", "django"),
    ("go", "google cloud"),
    ("git", "github"),
    ("git", "gitlab"),
    ("react", "reactive"),
    ("sql", "nosql"),
    ("sql", "mysql"),
    ("sql", "postgresql"),
    ("sql", "sqlite"),
    ("psql", "postgresql"),
    ("psql", "postgres"),
    ("c++", "c#"),
}


def normalize_skill_name(skill_name: Optional[str]) -> str:
    """
    Normalizes a skill name deterministically:
    1. Trims surrounding whitespace.
    2. Strips harmless surrounding punctuation.
    3. Collapses multiple inner whitespaces.
    4. Looks up canonical representation in the conservative alias map.
    5. Preserves clean original casing for unknown skills.

    Returns an empty string if input is None, empty, or whitespace-only.
    """
    if not skill_name:
        return ""

    # Strip whitespace and enclosing punctuation
    cleaned = skill_name.strip()
    # Strip harmless surrounding quotes, brackets, parens, trailing commas/dots
    cleaned = re.sub(r'^[^\w+#]+|[^\w+#]+$', '', cleaned)
    # Collapse multiple whitespaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    if not cleaned:
        return ""

    lookup_key = cleaned.lower()
    if lookup_key in CANONICAL_SKILL_MAP:
        return CANONICAL_SKILL_MAP[lookup_key]

    return cleaned


def canonical_skill_key(skill_name: Optional[str]) -> str:
    """
    Returns the lowercased comparison key for exact canonical matching.
    """
    normalized = normalize_skill_name(skill_name)
    return normalized.lower()


def skills_match(skill_a: Optional[str], skill_b: Optional[str]) -> bool:
    """
    Determines whether two skill names refer to the exact same skill or alias.
    Strictly avoids substring false positives (e.g. Java vs JavaScript, C vs C++).
    """
    key_a = canonical_skill_key(skill_a)
    key_b = canonical_skill_key(skill_b)

    if not key_a or not key_b:
        return False

    # Check explicitly disallowed pairs
    if (key_a, key_b) in DISALLOWED_COLLISIONS or (key_b, key_a) in DISALLOWED_COLLISIONS:
        return False

    return key_a == key_b


def find_matching_skill(query_skill: str, candidate_skills: Iterable[str]) -> Optional[str]:
    """
    Finds the first matching candidate skill from an iterable of skill names.
    Returns the original candidate skill name if a match is found, or None.
    """
    for candidate in candidate_skills:
        if skills_match(query_skill, candidate):
            return candidate
    return None
