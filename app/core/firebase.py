import base64
import json
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import auth, credentials, firestore

from app.core.config import get_settings


def initialize_firebase() -> None:
    if firebase_admin._apps:
        return

    settings = get_settings()
    app_options: dict[str, str] = {}
    if settings.firebase_project_id:
        app_options["projectId"] = settings.firebase_project_id

    service_account_input = settings.firebase_service_account_json

    if service_account_input:
        service_account_input = service_account_input.strip()

        # 1. File path
        if Path(service_account_input).is_file():
            credential = credentials.Certificate(service_account_input)
        else:
            # 2. Raw JSON string or Base64 string
            try:
                if service_account_input.startswith("{"):
                    cert_dict = json.loads(service_account_input)
                else:
                    decoded = base64.b64decode(service_account_input).decode("utf-8")
                    cert_dict = json.loads(decoded)
                credential = credentials.Certificate(cert_dict)
            except Exception as err:
                raise ValueError(
                    "Invalid FIREBASE_SERVICE_ACCOUNT_JSON format. Expected file path, JSON string, or Base64 string."
                ) from err
    else:
        # GCP Cloud Run / App Engine / Application Default Credentials (Option 2)
        credential = credentials.ApplicationDefault()

    firebase_admin.initialize_app(credential, app_options or None)


def get_firestore_client() -> Any:
    initialize_firebase()
    return firestore.client()


def verify_id_token(token: str) -> dict[str, Any]:
    initialize_firebase()
    return auth.verify_id_token(token)
