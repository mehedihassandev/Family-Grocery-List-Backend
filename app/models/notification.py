from typing import Any, Optional
from pydantic import BaseModel, Field


class DeviceTokenRequest(BaseModel):
    token: str = Field(..., description="FCM / Expo push token")
    device_type: Optional[str] = Field("android", description="Device platform e.g. android, ios, web")
    app_version: Optional[str] = Field(None, description="App version e.g. 1.0.0")


class NotificationItem(BaseModel):
    id: str = Field(..., description="Unique notification ID")
    familyId: str = Field(..., description="ID of the family group")
    recipientUid: str = Field(..., description="UID of the user receiving the notification")
    actorUid: str = Field(..., description="UID of the user who performed the action")
    actorName: str = Field(..., description="Name of the actor")
    title: str = Field(..., description="Notification title")
    body: str = Field(..., description="Notification message body")
    type: str = Field(..., description="Event type: ITEM_ADDED, ITEM_COMPLETED, ITEM_UPDATED, MEMBER_JOINED")
    data: dict[str, Any] = Field(default_factory=dict, description="Deep link metadata payload")
    isRead: bool = Field(default=False, description="Read state of the notification")
    createdAt: str = Field(..., description="ISO 8601 creation timestamp")


class NotificationListResponse(BaseModel):
    items: list[NotificationItem] = Field(default_factory=list)
    unreadCount: int = Field(default=0, description="Total unread notifications count")


class UnreadCountResponse(BaseModel):
    unreadCount: int = Field(default=0)


class MessageResponse(BaseModel):
    message: str
