from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.firebase import get_firestore_client, verify_id_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict[str, Any]:
    settings = get_settings()

    if credentials is None or credentials.scheme.lower() != "bearer":
        if settings.allow_dev_bypass:
            return {"uid": "dev-user-id", "name": "Dev User", "email": "dev@example.com"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token is required.",
        )

    try:
        return verify_id_token(credentials.credentials)
    except Exception as exc:
        if settings.allow_dev_bypass:
            return {"uid": "dev-user-id", "name": "Dev User", "email": "dev@example.com"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token is invalid or expired.",
        ) from exc


def ensure_family_access(family_id: str, current_user: dict[str, Any]) -> None:
    settings = get_settings()
    if settings.allow_dev_bypass and current_user.get("uid") == "dev-user-id":
        return

    # Check directly from custom token claims if present
    token_family_id = current_user.get("familyId") or current_user.get("family_id")
    if token_family_id == family_id:
        return

    uid = current_user.get("uid")
    if not isinstance(uid, str) or not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token is missing user id.",
        )

    user_snapshot = get_firestore_client().collection("users").document(uid).get()
    if not user_snapshot.exists:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User profile was not found.",
        )

    user_data = user_snapshot.to_dict() or {}
    user_family_id = user_data.get("familyId") or user_data.get("family_id")
    if user_family_id != family_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to this family.",
        )


