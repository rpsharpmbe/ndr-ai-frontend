import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Jira Backlog Chat")

class AskRequest(BaseModel):
    question: str

@app.get("/", response_class=HTMLResponse)
def home():
    return "<h1>Jira Backlog Chat is running</h1><p>Your deployment worked.</p>"

@app.post("/api/ask")
def ask(req: AskRequest):
    return {"answer": f"You asked: {req.question}"}
