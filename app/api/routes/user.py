from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models.family import User
from app.services.family import get_or_create_user_profile

router = APIRouter()


@router.get("/users/me", response_model=User)
def read_user_me(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> User:
    """Fetch logged-in user profile and current family membership state."""
    return get_or_create_user_profile(current_user)
