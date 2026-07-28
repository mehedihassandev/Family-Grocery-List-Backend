from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import ensure_family_access, get_current_user
from app.models.notification import (
    DeviceTokenRequest,
    MessageResponse,
    NotificationListResponse,
    UnreadCountResponse,
)
from app.services.notification import (
    get_unread_notification_count,
    list_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    register_device_token,
    remove_device_token,
)

router = APIRouter()


@router.post(
    "/users/me/device-tokens",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Register Device Token",
    description="Register an FCM / Expo push token for the current user's device.",
)
def add_device_token(
    payload: DeviceTokenRequest,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> MessageResponse:
    uid = current_user.get("uid", "")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token.")
    register_device_token(uid, payload)
    return MessageResponse(message="Device token registered successfully.")


@router.delete(
    "/users/me/device-tokens/{token}",
    response_model=MessageResponse,
    summary="Unregister Device Token",
    description="Remove an FCM / Expo push token on logout or app uninstall.",
)
def delete_device_token(
    token: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> MessageResponse:
    uid = current_user.get("uid", "")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token.")
    remove_device_token(uid, token)
    return MessageResponse(message="Device token removed successfully.")


@router.get(
    "/families/{family_id}/notifications",
    response_model=NotificationListResponse,
    summary="List Family Notifications",
    description="Fetch in-app notification feed for the current user in a family.",
)
def read_user_notifications(
    family_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    limit: int = 50,
) -> NotificationListResponse:
    ensure_family_access(family_id, current_user)
    uid = current_user.get("uid", "")
    return list_user_notifications(uid, family_id, limit=limit)


@router.get(
    "/families/{family_id}/notifications/unread-count",
    response_model=UnreadCountResponse,
    summary="Get Unread Notification Count",
    description="Fetch total unread notifications count for badge displays.",
)
def read_unread_count(
    family_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> UnreadCountResponse:
    ensure_family_access(family_id, current_user)
    uid = current_user.get("uid", "")
    count = get_unread_notification_count(uid, family_id)
    return UnreadCountResponse(unreadCount=count)


@router.patch(
    "/families/{family_id}/notifications/{notification_id}/read",
    response_model=MessageResponse,
    summary="Mark Notification As Read",
    description="Mark a specific notification as read.",
)
def set_notification_read(
    family_id: str,
    notification_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> MessageResponse:
    ensure_family_access(family_id, current_user)
    uid = current_user.get("uid", "")
    success = mark_notification_read(uid, notification_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    return MessageResponse(message="Notification marked as read.")


@router.post(
    "/families/{family_id}/notifications/read-all",
    response_model=MessageResponse,
    summary="Mark All Notifications As Read",
    description="Mark all unread notifications in this family as read.",
)
def set_all_notifications_read(
    family_id: str,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> MessageResponse:
    ensure_family_access(family_id, current_user)
    uid = current_user.get("uid", "")
    updated_count = mark_all_notifications_read(uid, family_id)
    return MessageResponse(message=f"Marked {updated_count} notifications as read.")
