from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import ensure_family_access, get_current_user
from app.models.family import (
    CreateFamilyRequest,
    Family,
    InviteMemberRequest,
    JoinFamilyRequest,
    MessageResponse,
    UpdateMemberRoleRequest,
    User,
)
from app.services.family import (
    create_family_service,
    get_family_members_service,
    get_family_service,
    invite_family_member_service,
    join_family_service,
    leave_family_service,
    remove_family_member_service,
    update_member_role_service,
)

router = APIRouter()


@router.post(
    "/families",
    response_model=Family,
    status_code=status.HTTP_201_CREATED,
)
def create_family(
    payload: CreateFamilyRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> Family:
    """Create a new family group."""
    try:
        return create_family_service(current_user, payload.name)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err


@router.post("/families/join", response_model=Family)
def join_family(
    payload: JoinFamilyRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> Family:
    """Join an existing family via invite code."""
    try:
        return join_family_service(current_user, payload.inviteCode)
    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite code",
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err


@router.get("/families/{family_id}", response_model=Family)
def read_family_metadata(
    family_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> Family:
    """Get metadata for a specific family."""
    ensure_family_access(family_id, current_user)
    family = get_family_service(family_id)
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found.",
        )
    return family


@router.get("/families/{family_id}/members", response_model=list[User])
def read_family_members(
    family_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> list[User]:
    """List all members of a family."""
    ensure_family_access(family_id, current_user)
    return get_family_members_service(family_id)


@router.post(
    "/families/{family_id}/members",
    response_model=MessageResponse,
    summary="Invite Family Member",
    description="Invite a user to a family group by email.",
)
def invite_family_member(
    family_id: str,
    payload: InviteMemberRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> MessageResponse:
    """Invite a user to a family group by email."""
    ensure_family_access(family_id, current_user)
    try:
        invite_family_member_service(current_user, family_id, payload.email)
        return MessageResponse(message="Invitation sent successfully.")
    except KeyError as err:
        detail_msg = err.args[0] if err.args else str(err)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail_msg,
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err


@router.patch(
    "/families/{family_id}/members/{user_id}/role",
    response_model=MessageResponse,
    summary="Update Family Member Role",
    description="Update a member's role within the family group (Owner only).",
)
def update_family_member_role(
    family_id: str,
    user_id: str,
    payload: UpdateMemberRoleRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> MessageResponse:
    """Update a member's role within the family group (Owner only)."""
    ensure_family_access(family_id, current_user)
    try:
        update_member_role_service(
            current_user, family_id, user_id, payload.role
        )
        return MessageResponse(message="Member role updated successfully.")
    except PermissionError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(err),
        ) from err
    except KeyError as err:
        detail_msg = err.args[0] if err.args else str(err)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail_msg,
        ) from err


@router.post("/families/{family_id}/leave", response_model=MessageResponse)
def leave_family(
    family_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> MessageResponse:
    """Leave the current family."""
    ensure_family_access(family_id, current_user)
    leave_family_service(current_user, family_id)
    return MessageResponse(message="Successfully left the family")


@router.delete(
    "/families/{family_id}/members/{user_id}", response_model=MessageResponse
)
def remove_family_member(
    family_id: str,
    user_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> MessageResponse:
    """Remove a member from the family (Owner only)."""
    ensure_family_access(family_id, current_user)
    try:
        remove_family_member_service(current_user, family_id, user_id)
        return MessageResponse(message="Member removed successfully")
    except PermissionError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(err),
        ) from err
    except KeyError as err:
        detail_msg = err.args[0] if err.args else str(err)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail_msg,
        ) from err

