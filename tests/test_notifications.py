from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.notification import (
    NotificationItem,
    NotificationListResponse,
)

client = TestClient(app)


@patch("app.api.routes.notification.register_device_token")
def test_add_device_token_api(mock_register: MagicMock) -> None:
    response = client.post(
        "/v1/users/me/device-tokens",
        json={"token": "test-fcm-token-123", "device_type": "android", "app_version": "1.0.0"},
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Device token registered successfully."}
    mock_register.assert_called_once()


@patch("app.api.routes.notification.remove_device_token")
def test_delete_device_token_api(mock_remove: MagicMock) -> None:
    response = client.delete("/v1/users/me/device-tokens/test-fcm-token-123")
    assert response.status_code == 200
    assert response.json() == {"message": "Device token removed successfully."}
    mock_remove.assert_called_once_with("dev-user-id", "test-fcm-token-123")


@patch("app.api.routes.notification.list_user_notifications")
def test_read_user_notifications_api(mock_list: MagicMock) -> None:
    mock_list.return_value = NotificationListResponse(
        items=[
            NotificationItem(
                id="notif-1",
                familyId="demo-family",
                recipientUid="demo-user-123",
                actorUid="user-456",
                actorName="Sarah",
                title="New Grocery Item Added",
                body="Sarah added 'Milk 2L' to the list.",
                type="ITEM_ADDED",
                data={"itemId": "item-123"},
                isRead=False,
                createdAt="2026-07-28T12:00:00Z",
            )
        ],
        unreadCount=1,
    )

    response = client.get("/v1/families/demo-family/notifications")
    assert response.status_code == 200
    data = response.json()
    assert data["unreadCount"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["actorName"] == "Sarah"


@patch("app.api.routes.notification.get_unread_notification_count")
def test_read_unread_count_api(mock_count: MagicMock) -> None:
    mock_count.return_value = 3
    response = client.get("/v1/families/demo-family/notifications/unread-count")
    assert response.status_code == 200
    assert response.json() == {"unreadCount": 3}


@patch("app.api.routes.notification.mark_notification_read")
def test_set_notification_read_api(mock_read: MagicMock) -> None:
    mock_read.return_value = True
    response = client.patch("/v1/families/demo-family/notifications/notif-1/read")
    assert response.status_code == 200
    assert response.json() == {"message": "Notification marked as read."}


@patch("app.api.routes.notification.mark_all_notifications_read")
def test_set_all_notifications_read_api(mock_read_all: MagicMock) -> None:
    mock_read_all.return_value = 5
    response = client.post("/v1/families/demo-family/notifications/read-all")
    assert response.status_code == 200
    assert response.json() == {"message": "Marked 5 notifications as read."}


@patch("app.services.notification.send_push_multicast")
@patch("app.services.notification.get_firestore_client")
def test_create_and_send_family_notification_self_exclusion(
    mock_get_db: MagicMock, mock_send_push: MagicMock
) -> None:
    from app.services.notification import create_and_send_family_notification

    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    # Mock 2 members: actor ("user-actor") and recipient ("user-recipient")
    doc_actor = MagicMock()
    doc_actor.id = "user-actor"
    doc_actor.to_dict.return_value = {"uid": "user-actor"}

    doc_recipient = MagicMock()
    doc_recipient.id = "user-recipient"
    doc_recipient.to_dict.return_value = {"uid": "user-recipient"}

    mock_db.collection().where().get.return_value = [doc_actor, doc_recipient]

    # Mock device token for recipient
    token_doc = MagicMock()
    token_doc.id = "recipient-fcm-token"
    mock_db.collection().document().collection().get.return_value = [token_doc]

    create_and_send_family_notification(
        family_id="demo-family",
        actor_uid="user-actor",
        actor_name="Mehedi",
        title="Item Added",
        body="Mehedi added Apples",
        event_type="ITEM_ADDED",
    )

    # Verify that notification was created for recipient only, NOT for actor (self-exclusion)
    mock_db.collection("users").document.assert_called_with("user-recipient")
    mock_send_push.assert_called_once()
    assert mock_send_push.call_args[0][0] == ["recipient-fcm-token"]
