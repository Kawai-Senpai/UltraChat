"""
UltraChat - Profile Service
Business logic for profile management.
"""

from typing import Optional, Dict, Any, List

from ..models import ProfileModel
from ..config import get_settings


class ProfileService:
    """
    Handles profile operations including:
    - CRUD operations for profiles
    - Profile duplication
    - Default profile management
    """
    
    def __init__(self):
        self.settings = get_settings()
    
    async def create_profile(
        self,
        name: str,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None,
        context_length: Optional[int] = None,
        model: Optional[str] = None,
        is_default: bool = False
    ) -> Dict[str, Any]:
        """Create a new profile with defaults from settings."""
        defaults = self.settings.chat_defaults
        
        return await ProfileModel.create(
            name=name,
            description=description,
            system_prompt=system_prompt,
            temperature=temperature if temperature is not None else defaults.temperature,
            top_p=top_p if top_p is not None else defaults.top_p,
            top_k=top_k if top_k is not None else defaults.top_k,
            max_tokens=max_tokens if max_tokens is not None else defaults.max_tokens,
            context_length=context_length if context_length is not None else defaults.context_length,
            model=model or self.settings.ollama.default_model,
            is_default=is_default
        )
    
    async def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get a profile by ID."""
        return await ProfileModel.get_by_id(profile_id)
    
    async def get_default_profile(self) -> Dict[str, Any]:
        """Get the default profile, creating one if needed."""
        return await ProfileModel.get_default()
    
    async def list_profiles(self) -> List[Dict[str, Any]]:
        """Get all profiles."""
        return await ProfileModel.get_all()
    
    async def update_profile(
        self,
        profile_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update a profile."""
        return await ProfileModel.update(profile_id, **kwargs)
    
    async def delete_profile(self, profile_id: str) -> Dict[str, Any]:
        """
        Delete a profile.
        Cannot delete the last profile.
        """
        profile = await ProfileModel.get_by_id(profile_id)
        if not profile:
            return {"success": False, "error": "Profile not found"}
        
        all_profiles = await ProfileModel.get_all()
        if len(all_profiles) <= 1:
            return {"success": False, "error": "Cannot delete the last profile"}
        
        success = await ProfileModel.delete(profile_id)
        if success:
            return {"success": True, "message": "Profile deleted"}
        return {"success": False, "error": "Failed to delete profile"}
    
    async def duplicate_profile(
        self,
        profile_id: str,
        new_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Duplicate a profile."""
        return await ProfileModel.duplicate(profile_id, new_name)
    
    async def set_default(self, profile_id: str) -> Dict[str, Any]:
        """Set a profile as the default."""
        profile = await ProfileModel.update(profile_id, is_default=True)
        if profile:
            return {"success": True, "profile": profile}
        return {"success": False, "error": "Failed to set default profile"}
    
    async def get_profile_templates(self) -> List[Dict[str, Any]]:
        """Get predefined profile templates."""
        return [
            {
                "name": "Creative Writer",
                "description": "For creative writing and storytelling",
                "system_prompt": "You are a creative writing assistant. Help with storytelling, character development, dialogue, and creative expression. Be imaginative and inspiring.",
                "temperature": 1.0,
                "top_p": 0.95
            },
            {
                "name": "Code Assistant",
                "description": "For programming and technical tasks",
                "system_prompt": "You are an expert programming assistant. Help with code writing, debugging, optimization, and technical explanations. Be precise and thorough.",
                "temperature": 0.3,
                "top_p": 0.8
            },
            {
                "name": "Analyst",
                "description": "For analysis and research tasks",
                "system_prompt": "You are a research and analysis assistant. Help with data interpretation, research summaries, and analytical thinking. Be objective and thorough.",
                "temperature": 0.5,
                "top_p": 0.85
            },
            {
                "name": "Tutor",
                "description": "For learning and education",
                "system_prompt": "You are a patient and knowledgeable tutor. Explain concepts clearly, provide examples, and adapt to the learner's level. Encourage questions and curiosity.",
                "temperature": 0.6,
                "top_p": 0.9
            },
            {
                "name": "Concise",
                "description": "For brief, to-the-point responses",
                "system_prompt": "You are a concise assistant. Provide brief, direct answers without unnecessary elaboration. Get straight to the point.",
                "temperature": 0.5,
                "top_p": 0.8,
                "max_tokens": 500
            }
        ]


# Global service instance
_profile_service: Optional[ProfileService] = None


def get_profile_service() -> ProfileService:
    """Get the global profile service instance."""
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service
