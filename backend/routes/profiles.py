"""
UltraChat - Profile Routes
API endpoints for profile management.
"""

from fastapi import APIRouter, HTTPException

from ..models.schemas import ProfileCreate, ProfileUpdate, ProfileResponse
from ..services import get_profile_service


router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("")
async def list_profiles():
    """Get all profiles."""
    service = get_profile_service()
    profiles = await service.list_profiles()
    return {"profiles": profiles}


@router.post("")
async def create_profile(data: ProfileCreate):
    """Create a new profile."""
    service = get_profile_service()
    profile = await service.create_profile(
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        temperature=data.temperature,
        top_p=data.top_p,
        top_k=data.top_k,
        max_tokens=data.max_tokens,
        context_length=data.context_length,
        model=data.model,
        is_default=data.is_default
    )
    return profile


@router.get("/default")
async def get_default_profile():
    """Get the default profile."""
    service = get_profile_service()
    return await service.get_default_profile()


@router.get("/templates")
async def get_templates():
    """Get profile templates."""
    service = get_profile_service()
    return {"templates": await service.get_profile_templates()}


@router.get("/{profile_id}")
async def get_profile(profile_id: str):
    """Get a profile by ID."""
    service = get_profile_service()
    profile = await service.get_profile(profile_id)
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return profile


@router.patch("/{profile_id}")
async def update_profile(profile_id: str, data: ProfileUpdate):
    """Update a profile."""
    service = get_profile_service()
    
    update_data = data.model_dump(exclude_unset=True)
    profile = await service.update_profile(profile_id, **update_data)
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return profile


@router.delete("/{profile_id}")
async def delete_profile(profile_id: str):
    """Delete a profile."""
    service = get_profile_service()
    result = await service.delete_profile(profile_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/{profile_id}/duplicate")
async def duplicate_profile(profile_id: str, new_name: str = None):
    """Duplicate a profile."""
    service = get_profile_service()
    profile = await service.duplicate_profile(profile_id, new_name)
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return profile


@router.post("/{profile_id}/set-default")
async def set_default(profile_id: str):
    """Set a profile as default."""
    service = get_profile_service()
    result = await service.set_default(profile_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result
