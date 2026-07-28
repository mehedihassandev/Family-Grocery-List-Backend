from datetime import UTC
from unittest.mock import MagicMock, patch

import pytest

from app.services.family import (
    create_family_service,
    get_family_members_service,
    get_family_service,
    get_or_create_user_profile,
    invite_family_member_service,
    join_family_service,
    leave_family_service,
    remove_family_member_service,
    update_member_role_service,
)


@patch("app.services.family.get_firestore_client")
def test_get_or_create_user_profile_existing(mock_fs: MagicMock) -> None:
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "uid": "user_123",
        "email": "user@example.com",
        "displayName": "User 123",
        "photoURL": None,
        "familyId": "fam_100",
        "role": "owner",
    }
    mock_fs.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

    user = get_or_create_user_profile({"uid": "user_123"})
    assert user.uid == "user_123"
    assert user.familyId == "fam_100"
    assert user.role == "owner"


@patch("app.services.family.get_firestore_client")
def test_get_or_create_user_profile_new(mock_fs: MagicMock) -> None:
    mock_doc = MagicMock()
    mock_doc.exists = False
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_fs.return_value.collection.return_value.document.return_value = mock_doc_ref

    user = get_or_create_user_profile(
        {"uid": "new_user", "email": "new@example.com", "name": "New User"}
    )
    assert user.uid == "new_user"
    assert user.email == "new@example.com"
    assert user.displayName == "New User"
    assert user.familyId is None
    assert user.role is None
    mock_doc_ref.set.assert_called_once()


@patch("app.services.family.get_or_create_user_profile")
@patch("app.services.family.get_firestore_client")
def test_create_family_service_success(
    mock_fs: MagicMock, mock_user: MagicMock
) -> None:
    from app.models.family import User

    mock_user.return_value = User(
        uid="user_abc",
        email="owner@example.com",
        displayName="Owner",
        familyId=None,
        role=None,
    )
    query_mock = mock_fs.return_value.collection.return_value.where.return_value.limit.return_value
    query_mock.get.return_value = []

    family = create_family_service({"uid": "user_abc"}, "The Smith Family")
    assert family.name == "The Smith Family"
    assert family.ownerId == "user_abc"
    assert len(family.inviteCode) == 6


@patch("app.services.family.get_or_create_user_profile")
@patch("app.services.family.get_firestore_client")
def test_create_family_service_already_member(
    mock_fs: MagicMock, mock_user: MagicMock
) -> None:
    from app.models.family import User

    mock_user.return_value = User(
        uid="user_abc",
        email="owner@example.com",
        displayName="Owner",
        familyId="fam_existing",
        role="member",
    )

    with pytest.raises(ValueError, match="User already belongs to a family."):
        create_family_service({"uid": "user_abc"}, "New Family")


@patch("app.services.family.get_or_create_user_profile")
@patch("app.services.family.get_firestore_client")
def test_join_family_service_success(
    mock_fs: MagicMock, mock_user: MagicMock
) -> None:
    from app.models.family import User

    mock_user.return_value = User(
        uid="user_xyz",
        email="member@example.com",
        displayName="Member",
        familyId=None,
        role=None,
    )

    fam_doc = MagicMock()
    fam_doc.to_dict.return_value = {
        "id": "fam_123",
        "name": "Smith Family",
        "inviteCode": "K9X2M4",
        "ownerId": "user_abc",
        "createdAt": "2026-07-27T16:20:00Z",
    }
    query_mock = mock_fs.return_value.collection.return_value.where.return_value.limit.return_value
    query_mock.get.return_value = [fam_doc]

    family = join_family_service({"uid": "user_xyz"}, "k9x2m4")
    assert family.id == "fam_123"
    assert family.inviteCode == "K9X2M4"


@patch("app.services.family.get_firestore_client")
def test_get_family_service(mock_fs: MagicMock) -> None:
    fam_doc = MagicMock()
    fam_doc.exists = True
    fam_doc.to_dict.return_value = {
        "id": "fam_123",
        "name": "Smith Family",
        "inviteCode": "K9X2M4",
        "ownerId": "user_abc",
        "createdAt": "2026-07-27T16:20:00Z",
    }
    mock_fs.return_value.collection.return_value.document.return_value.get.return_value = fam_doc

    family = get_family_service("fam_123")
    assert family is not None
    assert family.id == "fam_123"


@patch("app.services.family.get_firestore_client")
def test_get_family_service_datetime_with_nanoseconds(mock_fs: MagicMock) -> None:
    from google.api_core.datetime_helpers import DatetimeWithNanoseconds

    fam_doc = MagicMock()
    fam_doc.exists = True
    fam_doc.to_dict.return_value = {
        "id": "fam_123",
        "name": "Smith Family",
        "inviteCode": "K9X2M4",
        "ownerId": "user_abc",
        "createdAt": DatetimeWithNanoseconds(2026, 7, 27, 16, 20, 0, tzinfo=UTC),
    }
    mock_fs.return_value.collection.return_value.document.return_value.get.return_value = fam_doc

    family = get_family_service("fam_123")
    assert family is not None
    assert family.id == "fam_123"
    assert family.createdAt == "2026-07-27T16:20:00Z"


@patch("app.services.family.get_firestore_client")
def test_get_family_members_service(mock_fs: MagicMock) -> None:
    u1 = MagicMock()
    u1.id = "u1"
    u1.to_dict.return_value = {
        "uid": "u1",
        "email": "u1@example.com",
        "displayName": "User 1",
        "familyId": "fam_123",
        "role": "owner",
    }
    mock_fs.return_value.collection.return_value.where.return_value.get.return_value = [
        u1
    ]

    members = get_family_members_service("fam_123")
    assert len(members) == 1
    assert members[0].uid == "u1"


@patch("app.services.family.get_firestore_client")
def test_leave_family_service_owner_reassigns(mock_fs: MagicMock) -> None:
    user_doc = MagicMock()
    user_doc.exists = True
    user_doc.to_dict.return_value = {"role": "owner"}

    fam_doc = MagicMock()
    fam_doc.exists = True
    fam_doc.to_dict.return_value = {"ownerId": "owner_1"}

    rem1 = MagicMock()
    rem1.id = "member_2"
    rem1.to_dict.return_value = {"uid": "member_2", "role": "member"}

    db = mock_fs.return_value
    db.collection.return_value.document.return_value.get.side_effect = [
        user_doc,
        fam_doc,
    ]
    db.collection.return_value.where.return_value.get.return_value = [rem1]

    leave_family_service({"uid": "owner_1"}, "fam_123")
    db.collection.return_value.document.return_value.update.assert_called()


@patch("app.services.family.get_firestore_client")
def test_remove_family_member_service_permission_denied(mock_fs: MagicMock) -> None:
    fam_doc = MagicMock()
    fam_doc.exists = True
    fam_doc.to_dict.return_value = {"ownerId": "actual_owner"}

    mock_fs.return_value.collection.return_value.document.return_value.get.return_value = fam_doc

    with pytest.raises(PermissionError, match="Only family owner can remove members."):
        remove_family_member_service({"uid": "non_owner"}, "fam_123", "target_user")


@patch("app.services.family.get_firestore_client")
def test_invite_family_member_service_success(mock_fs: MagicMock) -> None:
    fam_doc = MagicMock()
    fam_doc.exists = True
    mock_fs.return_value.collection.return_value.document.return_value.get.return_value = fam_doc

    invite_family_member_service({"uid": "inviter"}, "fam_123", "newuser@example.com")
    mock_fs.return_value.collection.return_value.add.assert_called_once()


@patch("app.services.family.get_firestore_client")
def test_update_member_role_service_success(mock_fs: MagicMock) -> None:
    fam_doc = MagicMock()
    fam_doc.exists = True
    fam_doc.to_dict.return_value = {"ownerId": "owner_1"}

    target_doc = MagicMock()
    target_doc.exists = True
    target_doc.to_dict.return_value = {"familyId": "fam_123", "role": "member"}

    db = mock_fs.return_value
    target_ref = MagicMock()
    target_ref.get.return_value = target_doc

    def doc_side_effect(path: str) -> MagicMock:
        if path == "fam_123":
            fam_ref = MagicMock()
            fam_ref.get.return_value = fam_doc
            return fam_ref
        return target_ref

    db.collection.return_value.document.side_effect = doc_side_effect

    update_member_role_service({"uid": "owner_1"}, "fam_123", "target_user", "owner")
    target_ref.update.assert_called_with({"role": "owner"})

