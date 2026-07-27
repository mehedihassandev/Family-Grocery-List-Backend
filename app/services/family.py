import secrets
import string
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.firebase import get_firestore_client
from app.models.family import Family, User


def get_or_create_user_profile(current_user: dict[str, Any]) -> User:
    uid = current_user.get("uid", "")
    if not uid:
        raise ValueError("User ID is missing from credentials.")

    db = get_firestore_client()
    user_ref = db.collection("users").document(uid)
    doc = user_ref.get()

    if doc.exists:
        data = doc.to_dict() or {}
        return User(
            uid=data.get("uid", uid),
            email=data.get("email") or current_user.get("email", ""),
            displayName=data.get("displayName")
            or current_user.get("name")
            or current_user.get("displayName", "User"),
            photoURL=data.get("photoURL")
            or current_user.get("picture")
            or current_user.get("photoURL"),
            familyId=data.get("familyId") or data.get("family_id"),
            role=data.get("role"),
        )

    user_data = {
        "uid": uid,
        "email": current_user.get("email", ""),
        "displayName": current_user.get("name")
        or current_user.get("displayName", "User"),
        "photoURL": current_user.get("picture") or current_user.get("photoURL"),
        "familyId": None,
        "role": None,
    }
    user_ref.set(user_data)
    return User(**user_data)


def generate_unique_invite_code(db: Any) -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(10):
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        existing = (
            db.collection("families")
            .where("inviteCode", "==", code)
            .limit(1)
            .get()
        )
        if not existing:
            return code
    return "".join(secrets.choice(alphabet) for _ in range(6))


def create_family_service(current_user: dict[str, Any], name: str) -> Family:
    user = get_or_create_user_profile(current_user)
    if user.familyId:
        raise ValueError("User already belongs to a family.")

    db = get_firestore_client()
    invite_code = generate_unique_invite_code(db)
    family_id = f"fam_{uuid.uuid4().hex[:10]}"
    created_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    family_data = {
        "id": family_id,
        "name": name,
        "inviteCode": invite_code,
        "ownerId": user.uid,
        "createdAt": created_at,
    }

    db.collection("families").document(family_id).set(family_data)
    db.collection("users").document(user.uid).update(
        {"familyId": family_id, "role": "owner"}
    )

    return Family(**family_data)


def join_family_service(
    current_user: dict[str, Any], invite_code: str
) -> Family:
    normalized_code = invite_code.strip().upper()
    db = get_firestore_client()

    families = (
        db.collection("families")
        .where("inviteCode", "==", normalized_code)
        .limit(1)
        .get()
    )

    if not families:
        raise KeyError("Invalid invite code")

    user = get_or_create_user_profile(current_user)
    if user.familyId:
        raise ValueError("User already belongs to a family.")

    family_data = families[0].to_dict()
    family_id = family_data["id"]

    db.collection("users").document(user.uid).update(
        {"familyId": family_id, "role": "member"}
    )

    return Family(**family_data)


def get_family_service(family_id: str) -> Family | None:
    db = get_firestore_client()
    doc = db.collection("families").document(family_id).get()
    if not doc.exists:
        return None
    return Family(**doc.to_dict())


def get_family_members_service(family_id: str) -> list[User]:
    db = get_firestore_client()
    user_docs = db.collection("users").where("familyId", "==", family_id).get()
    members: list[User] = []
    for doc in user_docs:
        data = doc.to_dict() or {}
        members.append(
            User(
                uid=data.get("uid", doc.id),
                email=data.get("email", ""),
                displayName=data.get("displayName", ""),
                photoURL=data.get("photoURL"),
                familyId=data.get("familyId"),
                role=data.get("role"),
            )
        )
    return members


def leave_family_service(current_user: dict[str, Any], family_id: str) -> None:
    uid = current_user.get("uid", "")
    db = get_firestore_client()

    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    user_data = user_doc.to_dict() if user_doc.exists else {}

    user_role = user_data.get("role")

    # Clear user family membership
    user_ref.update({"familyId": None, "role": None})

    family_ref = db.collection("families").document(family_id)
    family_doc = family_ref.get()
    if not family_doc.exists:
        return

    family_data = family_doc.to_dict() or {}
    if user_role == "owner" or family_data.get("ownerId") == uid:
        remaining_docs = (
            db.collection("users").where("familyId", "==", family_id).get()
        )
        remaining = [
            d for d in remaining_docs if d.id != uid and d.to_dict().get("uid") != uid
        ]

        if remaining:
            next_owner_data = remaining[0].to_dict() or {}
            next_owner_id = next_owner_data.get("uid") or remaining[0].id
            db.collection("users").document(next_owner_id).update(
                {"role": "owner"}
            )
            family_ref.update({"ownerId": next_owner_id})
        else:
            family_ref.delete()


def remove_family_member_service(
    current_user: dict[str, Any], family_id: str, target_user_id: str
) -> None:
    uid = current_user.get("uid", "")
    db = get_firestore_client()

    family_doc = db.collection("families").document(family_id).get()
    if not family_doc.exists:
        raise KeyError("Family not found.")

    family_data = family_doc.to_dict() or {}
    if family_data.get("ownerId") != uid:
        raise PermissionError("Only family owner can remove members.")

    target_ref = db.collection("users").document(target_user_id)
    target_doc = target_ref.get()
    if not target_doc.exists:
        raise KeyError("Member not found.")

    target_data = target_doc.to_dict() or {}
    if target_data.get("familyId") != family_id:
        raise KeyError("Member does not belong to this family.")

    target_ref.update({"familyId": None, "role": None})
