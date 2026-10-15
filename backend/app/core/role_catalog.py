"""
InterviewIQ — Role Catalogue & Competency Requirement Schema
Defines standardized job roles, required technical competencies, expected proficiency levels,
and evaluation criteria for the student preparation platform.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class RoleCompetencyRequirement(BaseModel):
    skill_name: str = Field(..., description="Canonical name of the required competency")
    normalized_skill: str = Field(..., description="Normalized key for matching against resume skills")
    importance: str = Field(default="Core", description="'Core', 'Recommended', or 'Advanced'")
    expected_proficiency: str = Field(default="Intermediate", description="'Foundational', 'Intermediate', 'Advanced', 'Expert'")
    description: str = Field(..., description="Role-specific context and expected application of this competency")
    evaluation_criteria: str = Field(..., description="Rubric criteria used during interview evaluation")


class RoleDefinition(BaseModel):
    role_id: str
    role_name: str
    description: str
    experience_levels: List[str] = Field(default_factory=lambda: ["Entry-Level", "Mid-Level", "Senior", "Lead / Staff"])
    supported_question_types: List[str] = Field(default_factory=lambda: ["verbal", "coding", "system_design", "sql"])
    competencies: List[RoleCompetencyRequirement]


SUPPORTED_ROLES_CATALOG: Dict[str, RoleDefinition] = {
    "full_stack_engineer": RoleDefinition(
        role_id="full_stack_engineer",
        role_name="Full Stack Engineer",
        description="End-to-end web application development spanning modern frontend frameworks, backend APIs, relational/document databases, and production deployment.",
        competencies=[
            RoleCompetencyRequirement(
                skill_name="React / Frontend Frameworks",
                normalized_skill="React",
                importance="Core",
                expected_proficiency="Advanced",
                description="Component architecture, state management, reactive rendering, hook lifecycles, and client performance.",
                evaluation_criteria="Demonstrates component modularity, state normalization, error boundary handling, and rendering optimization.",
            ),
            RoleCompetencyRequirement(
                skill_name="Node.js / Backend Services",
                normalized_skill="Node.js",
                importance="Core",
                expected_proficiency="Advanced",
                description="RESTful/GraphQL API design, asynchronous event loops, middleware architectures, and secure request handling.",
                evaluation_criteria="Articulates request lifecycles, non-blocking I/O mechanics, error propagation, and API contracts.",
            ),
            RoleCompetencyRequirement(
                skill_name="Database Architecture (SQL & NoSQL)",
                normalized_skill="SQL",
                importance="Core",
                expected_proficiency="Intermediate",
                description="Schema normalization, index design, query optimization, ACID transactions, and data modeling.",
                evaluation_criteria="Designs relational tables with referential integrity, understands indexing strategies, and writes performant queries.",
            ),
            RoleCompetencyRequirement(
                skill_name="System Design & Web Architecture",
                normalized_skill="System Design",
                importance="Recommended",
                expected_proficiency="Intermediate",
                description="Scalable client-server topology, caching layers (Redis/CDN), authentication flows, and API rate limiting.",
                evaluation_criteria="Balances scalability vs complexity trade-offs, cache invalidation, and horizontal scaling strategies.",
            ),
            RoleCompetencyRequirement(
                skill_name="Testing & CI/CD",
                normalized_skill="Testing",
                importance="Recommended",
                expected_proficiency="Intermediate",
                description="Unit/integration testing suites, automated build pipelines, and regression prevention.",
                evaluation_criteria="Structures test coverage across boundary conditions, mocks I/O dependencies, and integrates automated checks.",
            ),
        ],
    ),
    "frontend_specialist": RoleDefinition(
        role_id="frontend_specialist",
        role_name="Frontend Specialist",
        description="Advanced client-side engineering focused on modern web platforms, component libraries, browser rendering mechanics, accessibility, and high performance.",
        competencies=[
            RoleCompetencyRequirement(
                skill_name="React / Next.js Architecture",
                normalized_skill="React",
                importance="Core",
                expected_proficiency="Advanced",
                description="Server/Client component boundaries, hydration lifecycles, custom hooks, and state reconciliation.",
                evaluation_criteria="Articulates virtual DOM reconciliation, memory leak prevention in hooks, and SSR/SSG rendering patterns.",
            ),
            RoleCompetencyRequirement(
                skill_name="TypeScript & Modern JavaScript",
                normalized_skill="TypeScript",
                importance="Core",
                expected_proficiency="Advanced",
                description="Strict type systems, generics, utility types, async event queues, and ECMAScript specifications.",
                evaluation_criteria="Leverages discriminating unions, avoids 'any' escapes, and details JavaScript execution context mechanics.",
            ),
            RoleCompetencyRequirement(
                skill_name="Web Performance & Core Web Vitals",
                normalized_skill="Web Performance",
                importance="Core",
                expected_proficiency="Intermediate",
                description="LCP/CLS/INP optimization, code-splitting, asset compression, lazy loading, and rendering pipeline profiling.",
                evaluation_criteria="Identifies layout thrashing causes, critical rendering path bottlenecks, and bundle size reduction techniques.",
            ),
            RoleCompetencyRequirement(
                skill_name="CSS Architecture & Responsive Design",
                normalized_skill="CSS",
                importance="Recommended",
                expected_proficiency="Advanced",
                description="Modern CSS (Grid, Flexbox, custom properties), responsive fluid layouts, and accessible UI patterns.",
                evaluation_criteria="Structures maintainable styling tokens, handles media queries, and adheres to WCAG accessibility guidelines.",
            ),
            RoleCompetencyRequirement(
                skill_name="State Management & Client Cache",
                normalized_skill="State Management",
                importance="Recommended",
                expected_proficiency="Intermediate",
                description="Global stores, client-side caching (React Query / SWR / Redux Toolkit), and optimistic UI updates.",
                evaluation_criteria="Selects appropriate state scopes (local vs global vs server cache) and manages mutation rollbacks.",
            ),
        ],
    ),
    "backend_systems": RoleDefinition(
        role_id="backend_systems",
        role_name="Backend Systems",
        description="High-throughput, reliable backend engineering focusing on microservices, distributed systems, concurrency, resilient data pipelines, and database optimization.",
        competencies=[
            RoleCompetencyRequirement(
                skill_name="Python / Go / Java Backend Services",
                normalized_skill="Python",
                importance="Core",
                expected_proficiency="Advanced",
                description="High-performance backend services, concurrency models, dependency injection, and modular service patterns.",
                evaluation_criteria="Demonstrates deep understanding of memory management, concurrent threading/goroutines/asyncio, and clean domain layering.",
            ),
            RoleCompetencyRequirement(
                skill_name="Distributed System Architecture",
                normalized_skill="Distributed Systems",
                importance="Core",
                expected_proficiency="Advanced",
                description="CAP theorem, consensus protocols, message brokers (Kafka/RabbitMQ), idempotency, and partition tolerance.",
                evaluation_criteria="Architects fault-tolerant communication, designs at-least-once processing idempotency, and mitigates split-brain scenarios.",
            ),
            RoleCompetencyRequirement(
                skill_name="Database Internals & Optimization",
                normalized_skill="PostgreSQL",
                importance="Core",
                expected_proficiency="Advanced",
                description="Query execution plans, B-Tree vs Hash indexes, transaction isolation levels, connection pooling, and replication lag.",
                evaluation_criteria="Analyzes EXPLAIN outputs, mitigates deadlocks, selects appropriate transaction isolation, and configures read replicas.",
            ),
            RoleCompetencyRequirement(
                skill_name="API Design & Protocol Architecture",
                normalized_skill="REST APIs",
                importance="Core",
                expected_proficiency="Advanced",
                description="gRPC, REST, WebSockets, protocol buffers, payload serialization, and strict schema validation.",
                evaluation_criteria="Chooses optimal transport protocols, defines backward-compatible schema contracts, and implements rate limiting.",
            ),
            RoleCompetencyRequirement(
                skill_name="Observability & Reliability",
                normalized_skill="Observability",
                importance="Recommended",
                expected_proficiency="Intermediate",
                description="Distributed tracing, structured logging, health checks, circuit breakers, and telemetry metrics.",
                evaluation_criteria="Implements circuit-breaker patterns, configures SLI/SLO alerts, and traces cross-service latency bottlenecks.",
            ),
        ],
    ),
    "ai_ml_engineer": RoleDefinition(
        role_id="ai_ml_engineer",
        role_name="AI/ML Engineer",
        description="Machine learning engineering and production AI systems: data pipelines, model training/fine-tuning, LLM orchestration, evaluation metrics, and low-latency inference.",
        competencies=[
            RoleCompetencyRequirement(
                skill_name="Machine Learning Foundations & Deep Learning",
                normalized_skill="Machine Learning",
                importance="Core",
                expected_proficiency="Advanced",
                description="Supervised/unsupervised algorithms, loss functions, gradient descent mechanics, transformers, and overfitting mitigation.",
                evaluation_criteria="Explains mathematical foundations, diagnoses variance vs bias, and selects suitable model architectures.",
            ),
            RoleCompetencyRequirement(
                skill_name="PyTorch / TensorFlow Modeling",
                normalized_skill="PyTorch",
                importance="Core",
                expected_proficiency="Advanced",
                description="Custom layers, data loaders, training loops, GPU tensor acceleration, and checkpointing.",
                evaluation_criteria="Writes clean tensor operations, handles distributed training synchronization, and manages gradient accumulation.",
            ),
            RoleCompetencyRequirement(
                skill_name="LLM Orchestration & Prompt Architecture",
                normalized_skill="LLM",
                importance="Core",
                expected_proficiency="Intermediate",
                description="Retrieval-Augmented Generation (RAG), vector embeddings, context window management, and structured generation.",
                evaluation_criteria="Designs semantic chunking strategies, guards against prompt injection, and measures retrieval precision/recall.",
            ),
            RoleCompetencyRequirement(
                skill_name="Data Processing & Feature Engineering",
                normalized_skill="Data Pipelines",
                importance="Core",
                expected_proficiency="Advanced",
                description="Pandas/Polars data pipelines, feature scaling, handling missing values, and dataset validation.",
                evaluation_criteria="Detects data leakage, handles skewed distributions, and parallelizes batch transformation pipelines.",
            ),
            RoleCompetencyRequirement(
                skill_name="Model Serving & Production Inference",
                normalized_skill="Model Serving",
                importance="Recommended",
                expected_proficiency="Intermediate",
                description="ONNX quantization, batch inference optimization, latency budgeting, and model monitoring drift.",
                evaluation_criteria="Reduces inference memory footprint, optimizes throughput vs latency, and monitors prediction drift.",
            ),
        ],
    ),
    "devops_cloud": RoleDefinition(
        role_id="devops_cloud",
        role_name="DevOps & Cloud",
        description="Cloud infrastructure, containerization, orchestration, continuous delivery pipelines, security compliance, and platform reliability engineering.",
        competencies=[
            RoleCompetencyRequirement(
                skill_name="Docker & Containerization",
                normalized_skill="Docker",
                importance="Core",
                expected_proficiency="Advanced",
                description="Multi-stage builds, image optimization, container security, volume mounts, and network namespaces.",
                evaluation_criteria="Creates minimal non-root container images, optimizes layer caching, and secures container runtimes.",
            ),
            RoleCompetencyRequirement(
                skill_name="Kubernetes & Container Orchestration",
                normalized_skill="Kubernetes",
                importance="Core",
                expected_proficiency="Advanced",
                description="Pods, Deployments, Services, Ingress controllers, ConfigMaps, Secrets, HPA, and rolling zero-downtime updates.",
                evaluation_criteria="Configures liveness/readiness probes, resource requests/limits, and manages stateful workloads resiliently.",
            ),
            RoleCompetencyRequirement(
                skill_name="Infrastructure as Code (Terraform / CloudFormation)",
                normalized_skill="Terraform",
                importance="Core",
                expected_proficiency="Intermediate",
                description="Declarative infrastructure, state management, module design, and immutable infrastructure patterns.",
                evaluation_criteria="Manages remote state locking, structures reusable modules, and prevents configuration drift.",
            ),
            RoleCompetencyRequirement(
                skill_name="CI/CD Pipelines & Automation",
                normalized_skill="CI/CD",
                importance="Core",
                expected_proficiency="Advanced",
                description="GitHub Actions/GitLab CI, artifact registries, automated test gates, canary/blue-green deployments.",
                evaluation_criteria="Designs parallel test pipelines, implements automated rollback triggers, and protects release environments.",
            ),
            RoleCompetencyRequirement(
                skill_name="Cloud Security & IAM",
                normalized_skill="Cloud Security",
                importance="Recommended",
                expected_proficiency="Intermediate",
                description="Principle of least privilege, role-based access control, secret management (Vault/KMS), and VPC network isolation.",
                evaluation_criteria="Audits IAM permission boundaries, avoids hardcoded secrets, and isolates private subnets.",
            ),
        ],
    ),
}


def normalize_role_key(role_input: str) -> str:
    """Normalize input role string into a canonical role_id."""
    clean = (role_input or "").strip().lower().replace("-", " ").replace("_", " ")
    if "full" in clean or "stack" in clean:
        return "full_stack_engineer"
    if "front" in clean or "ui" in clean:
        return "frontend_specialist"
    if "back" in clean or "systems" in clean or "system" in clean:
        return "backend_systems"
    if "ai" in clean or "ml" in clean or "machine" in clean or "data sci" in clean:
        return "ai_ml_engineer"
    if "devops" in clean or "cloud" in clean or "infra" in clean or "sre" in clean:
        return "devops_cloud"
    return ""


def get_supported_roles() -> List[Dict[str, Any]]:
    """Return all supported roles as structured list for client consumption."""
    return [role.model_dump() for role in SUPPORTED_ROLES_CATALOG.values()]


def get_role_definition(role_input: str) -> Optional[RoleDefinition]:
    """Retrieve full role definition by key or title."""
    key = normalize_role_key(role_input)
    if key and key in SUPPORTED_ROLES_CATALOG:
        return SUPPORTED_ROLES_CATALOG[key]
    return None


def is_valid_role(role_input: str) -> bool:
    """Check if given role string maps to a supported catalog role."""
    return get_role_definition(role_input) is not None
