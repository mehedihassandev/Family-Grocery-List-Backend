from datetime import UTC, datetime
import logging
from typing import Any
import uuid

from firebase_admin import messaging

from app.core.firebase import get_firestore_client
from app.models.notification import (
    DeviceTokenRequest,
    NotificationItem,
    NotificationListResponse,
)

logger = logging.getLogger(__name__)


def register_device_token(uid: str, payload: DeviceTokenRequest) -> None:
    db = get_firestore_client()
    now = datetime.now(UTC).isoformat()
    token_ref = db.collection("users").document(uid).collection("tokens").document(payload.token)
    token_ref.set(
        {
            "token": payload.token,
            "deviceType": payload.device_type,
            "appVersion": payload.app_version,
            "updatedAt": now,
        }
    )


def remove_device_token(uid: str, token: str) -> None:
    db = get_firestore_client()
    db.collection("users").document(uid).collection("tokens").document(token).delete()


def get_user_device_tokens(uid: str) -> list[str]:
    db = get_firestore_client()
    token_docs = db.collection("users").document(uid).collection("tokens").get()
    return [doc.id for doc in token_docs if doc.id]


def send_push_multicast(tokens: list[str], title: str, body: str, data: dict[str, Any]) -> None:
    if not tokens:
        return

    string_data = {k: str(v) if v is not None else "" for k, v in data.items()}

    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=string_data,
    )

    try:
        response = messaging.send_each_for_multicast(message)
        logger.info(
            "FCM Multicast sent: %d successful, %d failed",
            response.success_count,
            response.failure_count,
        )
    except Exception as err:
        logger.warning("FCM Push delivery notification failed or skipped: %s", err)


def create_and_send_family_notification(
    family_id: str,
    actor_uid: str,
    actor_name: str,
    title: str,
    body: str,
    event_type: str,
    data: dict[str, Any] | None = None,
) -> None:
    db = get_firestore_client()
    payload_data = data or {}
    now = datetime.now(UTC).isoformat()

    # 1. Fetch all family members
    user_docs = db.collection("users").where("familyId", "==", family_id).get()
    recipients = [
        doc.id for doc in user_docs if doc.id != actor_uid and doc.to_dict().get("uid") != actor_uid
    ]

    if not recipients:
        return

    all_tokens: list[str] = []

    # 2. Persist in-app notification for each recipient & collect tokens
    for recipient_uid in recipients:
        notif_id = f"notif_{uuid.uuid4().hex[:12]}"
        notif_dict = {
            "id": notif_id,
            "familyId": family_id,
            "recipientUid": recipient_uid,
            "actorUid": actor_uid,
            "actorName": actor_name,
            "title": title,
            "body": body,
            "type": event_type,
            "data": payload_data,
            "isRead": False,
            "createdAt": now,
        }
        db.collection("users").document(recipient_uid).collection("notifications").document(
            notif_id
        ).set(notif_dict)

        # Collect user device tokens
        user_tokens = get_user_device_tokens(recipient_uid)
        all_tokens.extend(user_tokens)

    # 3. Send out FCM push notification to all collected tokens
    if all_tokens:
        send_push_multicast(all_tokens, title, body, payload_data)


def list_user_notifications(
    uid: str, family_id: str, limit: int = 50
) -> NotificationListResponse:
    db = get_firestore_client()
    notif_docs = (
        db.collection("users")
        .document(uid)
        .collection("notifications")
        .where("familyId", "==", family_id)
        .get()
    )

    items: list[NotificationItem] = []
    unread_count = 0

    for doc in notif_docs:
        data = doc.to_dict() or {}
        data.setdefault("id", doc.id)
        item = NotificationItem.model_validate(data)
        items.append(item)
        if not item.isRead:
            unread_count += 1

    # Sort descending by createdAt
    items.sort(key=lambda x: x.createdAt, reverse=True)
    return NotificationListResponse(items=items[:limit], unreadCount=unread_count)


def mark_notification_read(uid: str, notification_id: str) -> bool:
    db = get_firestore_client()
    doc_ref = (
        db.collection("users")
        .document(uid)
        .collection("notifications")
        .document(notification_id)
    )
    doc = doc_ref.get()
    if not doc.exists:
        return False
    doc_ref.update({"isRead": True})
    return True


def mark_all_notifications_read(uid: str, family_id: str) -> int:
    db = get_firestore_client()
    notif_docs = (
        db.collection("users")
        .document(uid)
        .collection("notifications")
        .where("familyId", "==", family_id)
        .where("isRead", "==", False)
        .get()
    )

    updated_count = 0
    for doc in notif_docs:
        doc.reference.update({"isRead": True})
        updated_count += 1

    return updated_count


def get_unread_notification_count(uid: str, family_id: str) -> int:
    db = get_firestore_client()
    notif_docs = (
        db.collection("users")
        .document(uid)
        .collection("notifications")
        .where("familyId", "==", family_id)
        .where("isRead", "==", False)
        .get()
    )
    return len(notif_docs)
