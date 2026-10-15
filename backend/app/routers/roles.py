import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status

from app.core.role_catalog import (
    get_supported_roles,
    get_role_definition,
    RoleDefinition,
)

logger = logging.getLogger("interviewiq.roles_router")

router = APIRouter(prefix="/api/roles", tags=["Role Catalogue & Competencies"])


@router.get(
    "",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get All Supported Target Job Roles",
    description="Returns the standardized catalog of supported job preparation roles and their core competencies.",
)
async def list_supported_roles() -> List[Dict[str, Any]]:
    """Retrieve all supported roles with their competency benchmarks."""
    return get_supported_roles()


@router.get(
    "/{role_name}",
    status_code=status.HTTP_200_OK,
    summary="Get Specific Role Competency Requirements",
    description="Returns the standardized competency requirement schema for a specific job role.",
)
async def get_role_details(role_name: str) -> Dict[str, Any]:
    """Retrieve standardized competency requirements and expected proficiencies for a role."""
    role_def = get_role_definition(role_name)
    if not role_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Role '{role_name}' is not in the supported catalogue. "
                "Supported roles: Full Stack Engineer, Frontend Specialist, Backend Systems, AI/ML Engineer, DevOps & Cloud."
            ),
        )
    return role_def.model_dump()
