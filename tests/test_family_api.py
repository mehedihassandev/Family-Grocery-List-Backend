from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.family import Family, User

client = TestClient(app)


@patch("app.api.routes.user.get_or_create_user_profile")
def test_read_user_me_api(mock_get_user: MagicMock) -> None:
    mock_get_user.return_value = User(
        uid="dev-user-id",
        email="dev@example.com",
        displayName="Dev User",
        photoURL="https://example.com/avatar.jpg",
        familyId="fam_12345",
        role="owner",
    )

    response = client.get("/v1/users/me")
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == "dev-user-id"
    assert data["email"] == "dev@example.com"
    assert data["displayName"] == "Dev User"
    assert data["photoURL"] == "https://example.com/avatar.jpg"
    assert data["familyId"] == "fam_12345"
    assert data["role"] == "owner"


@patch("app.api.routes.family.create_family_service")
def test_create_family_api_success(mock_create: MagicMock) -> None:
    mock_create.return_value = Family(
        id="fam_12345",
        name="Smith Family",
        inviteCode="K9X2M4",
        ownerId="user_abc",
        createdAt="2026-07-27T16:20:00Z",
    )

    payload = {"name": "Smith Family"}
    response = client.post("/v1/families", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "fam_12345"
    assert data["name"] == "Smith Family"
    assert data["inviteCode"] == "K9X2M4"
    assert data["ownerId"] == "user_abc"
    assert data["createdAt"] == "2026-07-27T16:20:00Z"


@patch("app.api.routes.family.create_family_service")
def test_create_family_api_already_in_family(mock_create: MagicMock) -> None:
    mock_create.side_effect = ValueError("User already belongs to a family.")

    payload = {"name": "Smith Family"}
    response = client.post("/v1/families", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "User already belongs to a family."


@patch("app.api.routes.family.join_family_service")
def test_join_family_api_success(mock_join: MagicMock) -> None:
    mock_join.return_value = Family(
        id="fam_12345",
        name="Smith Family",
        inviteCode="K9X2M4",
        ownerId="user_abc",
        createdAt="2026-07-27T16:20:00Z",
    )

    payload = {"inviteCode": "k9x2m4"}
    response = client.post("/v1/families/join", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "fam_12345"
    assert data["inviteCode"] == "K9X2M4"


@patch("app.api.routes.family.join_family_service")
def test_join_family_api_invalid_code(mock_join: MagicMock) -> None:
    mock_join.side_effect = KeyError("Invalid invite code")

    payload = {"inviteCode": "INVALID"}
    response = client.post("/v1/families/join", json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Invalid invite code"


@patch("app.api.routes.family.join_family_service")
def test_join_family_api_already_in_family(mock_join: MagicMock) -> None:
    mock_join.side_effect = ValueError("User already belongs to a family.")

    payload = {"inviteCode": "K9X2M4"}
    response = client.post("/v1/families/join", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "User already belongs to a family."


@patch("app.api.routes.family.get_family_service")
@patch("app.api.routes.family.ensure_family_access")
def test_get_family_metadata_api_success(
    mock_access: MagicMock, mock_get: MagicMock
) -> None:
    mock_get.return_value = Family(
        id="fam_12345",
        name="Smith Family",
        inviteCode="K9X2M4",
        ownerId="user_abc",
        createdAt="2026-07-27T16:20:00Z",
    )

    response = client.get("/v1/families/fam_12345")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "fam_12345"
    assert data["name"] == "Smith Family"


@patch("app.api.routes.family.get_family_service")
@patch("app.api.routes.family.ensure_family_access")
def test_get_family_metadata_api_not_found(
    mock_access: MagicMock, mock_get: MagicMock
) -> None:
    mock_get.return_value = None

    response = client.get("/v1/families/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Family not found."


@patch("app.api.routes.family.get_family_members_service")
@patch("app.api.routes.family.ensure_family_access")
def test_get_family_members_api_success(
    mock_access: MagicMock, mock_members: MagicMock
) -> None:
    mock_members.return_value = [
        User(
            uid="user_abc",
            email="owner@example.com",
            displayName="Owner User",
            familyId="fam_12345",
            role="owner",
        ),
        User(
            uid="user_xyz",
            email="member@example.com",
            displayName="Member User",
            familyId="fam_12345",
            role="member",
        ),
    ]

    response = client.get("/v1/families/fam_12345/members")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["role"] == "owner"
    assert data[1]["role"] == "member"


@patch("app.api.routes.family.leave_family_service")
@patch("app.api.routes.family.ensure_family_access")
def test_leave_family_api_success(
    mock_access: MagicMock, mock_leave: MagicMock
) -> None:
    response = client.post("/v1/families/fam_12345/leave")
    assert response.status_code == 200
    assert response.json() == {"message": "Successfully left the family"}


@patch("app.api.routes.family.remove_family_member_service")
@patch("app.api.routes.family.ensure_family_access")
def test_remove_family_member_api_success(
    mock_access: MagicMock, mock_remove: MagicMock
) -> None:
    response = client.delete("/v1/families/fam_12345/members/user_xyz")
    assert response.status_code == 200
    assert response.json() == {"message": "Member removed successfully"}


@patch("app.api.routes.family.remove_family_member_service")
@patch("app.api.routes.family.ensure_family_access")
def test_remove_family_member_api_forbidden(
    mock_access: MagicMock, mock_remove: MagicMock
) -> None:
    mock_remove.side_effect = PermissionError("Only family owner can remove members.")

    response = client.delete("/v1/families/fam_12345/members/user_xyz")
    assert response.status_code == 403
    assert response.json()["detail"] == "Only family owner can remove members."


@patch("app.api.routes.family.remove_family_member_service")
@patch("app.api.routes.family.ensure_family_access")
def test_remove_family_member_api_not_found(
    mock_access: MagicMock, mock_remove: MagicMock
) -> None:
    mock_remove.side_effect = KeyError("Member not found.")

    response = client.delete("/v1/families/fam_12345/members/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Member not found."


@patch("app.api.routes.family.invite_family_member_service")
@patch("app.api.routes.family.ensure_family_access")
def test_invite_family_member_api_success(
    mock_access: MagicMock, mock_invite: MagicMock
) -> None:
    payload = {"email": "user@example.com"}
    response = client.post("/v1/families/fam_12345/members", json=payload)
    assert response.status_code == 200
    assert response.json() == {"message": "Invitation sent successfully."}


@patch("app.api.routes.family.invite_family_member_service")
@patch("app.api.routes.family.ensure_family_access")
def test_invite_family_member_api_not_found(
    mock_access: MagicMock, mock_invite: MagicMock
) -> None:
    mock_invite.side_effect = KeyError("Family not found.")
    payload = {"email": "user@example.com"}
    response = client.post("/v1/families/nonexistent/members", json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Family not found."


@patch("app.api.routes.family.update_member_role_service")
@patch("app.api.routes.family.ensure_family_access")
def test_update_member_role_api_success(
    mock_access: MagicMock, mock_update_role: MagicMock
) -> None:
    payload = {"role": "owner"}
    response = client.patch(
        "/v1/families/fam_12345/members/user_xyz/role", json=payload
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Member role updated successfully."}


@patch("app.api.routes.family.update_member_role_service")
@patch("app.api.routes.family.ensure_family_access")
def test_update_member_role_api_forbidden(
    mock_access: MagicMock, mock_update_role: MagicMock
) -> None:
    mock_update_role.side_effect = PermissionError(
        "Only family owner can update member roles."
    )
    payload = {"role": "owner"}
    response = client.patch(
        "/v1/families/fam_12345/members/user_xyz/role", json=payload
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Only family owner can update member roles."


@patch("app.api.routes.family.update_member_role_service")
@patch("app.api.routes.family.ensure_family_access")
def test_update_member_role_api_not_found(
    mock_access: MagicMock, mock_update_role: MagicMock
) -> None:
    mock_update_role.side_effect = KeyError("Member not found.")
    payload = {"role": "member"}
    response = client.patch(
        "/v1/families/fam_12345/members/nonexistent/role", json=payload
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Member not found."

