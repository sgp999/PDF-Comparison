# FastAPI Starter App

A minimal FastAPI application scaffold.

## Setup

```bash
cd fastapi-app
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## API routes

- `GET /` - root welcome message
- `GET /api/hello` - hello message
- `GET /api/items/{item_id}` - read item by id
- `POST /api/items` - create item JSON payload

## Example POST body

```json
{
  "id": 1,
  "name": "Sample Item",
  "description": "A test item"
}
```
