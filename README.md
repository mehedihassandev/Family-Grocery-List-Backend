# Python Data Backend & Firebase Automation API

FastAPI service for server-side grocery data work and Firebase management. It uses Firebase Admin SDK to directly manipulate Cloud Firestore without needing to manually open the Firebase Web Console.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Set `FIREBASE_SERVICE_ACCOUNT_JSON` or `FIREBASE_PROJECT_ID` in `backend/.env`.

## Run

```bash
uvicorn app.main:app --reload
```

Local API & Interactive Swagger Documentation:

- **Interactive API Docs (Swagger UI)**: `http://127.0.0.1:8000/docs`
- **Alternative Docs (ReDoc)**: `http://127.0.0.1:8000/redoc`

Mobile app `.env`:

```env
EXPO_PUBLIC_DATA_API_BASE_URL=http://127.0.0.1:8000
```

*(Use `http://10.0.2.2:8000` for Android emulator)*

## Available Endpoints (No Firebase Console Needed!)

| HTTP Method | Route | Description |
| :--- | :--- | :--- |
| **GET** | `/health` | Server health check |
| **GET** | `/v1/families/{family_id}/items` | List all grocery items for a family |
| **POST** | `/v1/families/{family_id}/items` | Add a new item directly to Firestore |
| **GET** | `/v1/families/{family_id}/items/{item_id}` | Get item details |
| **PATCH** | `/v1/families/{family_id}/items/{item_id}` | Update item status, priority, or notes |
| **DELETE** | `/v1/families/{family_id}/items/{item_id}` | Delete item from Firestore |
| **POST** | `/v1/families/{family_id}/seed` | **Instant Seed**: Adds 5 sample grocery items to Firestore with 1 click |
| **GET** | `/v1/families/{family_id}/grocery-summary` | Aggregated summary stats (totals, pending, urgent) |

## Quick Start for Learning Python & Testing Firebase

1. Open **`http://127.0.0.1:8000/docs`** in your browser.
2. Click on **`POST /v1/families/{family_id}/seed`**.
3. Enter your `family_id` (e.g., `family-123`) and click **Execute**.
4. Check **`GET /v1/families/{family_id}/items`** to see your live Firestore items instantly!

## 100% Free Render.com Deployment

1. Push your repository to GitHub.
2. Sign in to [Render.com](https://dashboard.render.com/).
3. Click **New +** -> **Blueprint**, and select your GitHub repository.
4. Render will automatically detect `render.yaml` and deploy your FastAPI backend on the **Free Tier**.
5. Once deployed, copy your free HTTPS API URL (e.g. `https://family-grocery-data-api.onrender.com`) and update `EXPO_PUBLIC_DATA_API_BASE_URL` in your root `.env`.


