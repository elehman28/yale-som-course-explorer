"""Yale SOM course explorer API desk.

Run from backend/:  uvicorn main:app --reload --port 8000
Open API docs:      http://127.0.0.1:8000/docs
Frontend (Vite):    http://127.0.0.1:5173
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import auth
from agent import run_agent
from db import init_db

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA_PATH = ROOT / "data" / "yale_som_classes.json"
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

app = FastAPI(title="Yale SOM Courses", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create the users/sessions/chats tables if they do not exist yet.
init_db()


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """Resolve the Bearer token to a user, or 401."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    user = auth.user_for_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user


def load_courses() -> list[dict]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str
    tools_used: list[str] = Field(default_factory=list)


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=200)


class Session(BaseModel):
    token: str
    username: str


class HistoryMessage(BaseModel):
    role: str
    content: str
    tools_used: list[str] = Field(default_factory=list)
    created_at: str | None = None


@app.get("/api/health")
def health():
    return {"ok": True, "courses_file": str(DATA_PATH.name)}


@app.get("/api/courses")
def list_courses(q: str | None = Query(default=None)):
    """Return courses for the React catalog (optional text filter)."""
    courses = load_courses()
    if not q:
        return {"count": len(courses), "courses": courses}
    needle = q.lower().strip()
    matched = [
        c
        for c in courses
        if needle in json.dumps(c, ensure_ascii=False).lower()
    ]
    return {"count": len(matched), "courses": matched}


@app.post("/api/signup", response_model=Session)
def signup(body: Credentials):
    try:
        session = auth.create_user(body.username, body.password)
    except auth.AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Session(token=session["token"], username=session["username"])


@app.post("/api/login", response_model=Session)
def login(body: Credentials):
    try:
        session = auth.login(body.username, body.password)
    except auth.AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return Session(token=session["token"], username=session["username"])


@app.post("/api/logout")
def logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.lower().startswith("bearer "):
        auth.logout(authorization.split(" ", 1)[1].strip())
    return {"ok": True}


@app.get("/api/me", response_model=Session)
def me(user: dict = Depends(current_user), authorization: str | None = Header(default=None)):
    token = authorization.split(" ", 1)[1].strip() if authorization else ""
    return Session(token=token, username=user["username"])


@app.get("/api/history", response_model=list[HistoryMessage])
def get_history(user: dict = Depends(current_user)):
    """Past messages for the signed-in user, oldest first."""
    return [HistoryMessage(**m) for m in auth.history(user["user_id"])]


@app.delete("/api/history")
def delete_history(user: dict = Depends(current_user)):
    return {"deleted": auth.clear_history(user["user_id"])}


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest, user: dict = Depends(current_user)):
    """Answer a question and persist both sides of the exchange."""
    auth.save_message(user["user_id"], "user", body.message)
    result = run_agent(body.message)
    reply = result.get("reply", "")
    tools_used = list(result.get("tools_used") or [])
    auth.save_message(user["user_id"], "assistant", reply, tools_used)
    return ChatResponse(reply=reply, tools_used=tools_used)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
