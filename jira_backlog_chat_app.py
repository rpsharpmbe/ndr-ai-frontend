import os
from typing import Any, Dict, List

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY", "")
SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "jira-issues-v2")
SEARCH_API_VERSION = os.getenv("AZURE_SEARCH_API_VERSION", "2024-07-01")
SEARCH_SEMANTIC_CONFIG = os.getenv("AZURE_SEARCH_SEMANTIC_CONFIG", "jira-semantic")
SEARCH_TOP_K = int(os.getenv("AZURE_SEARCH_TOP_K", "5"))

AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
AOAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AOAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
AOAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")

app = FastAPI(title="Jira Backlog Chat")


class AskRequest(BaseModel):
    question: str


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <html>
      <head><title>Jira Backlog Chat</title></head>
      <body style="font-family: Arial; max-width: 900px; margin: 40px auto;">
        <h1>Jira Backlog Chat</h1>
        <p>The app is running.</p>
      </body>
    </html>
    """


def search_backlog(question: str) -> Dict[str, Any]:
    url = f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/search?api-version={SEARCH_API_VERSION}"
    headers = {
        "Content-Type": "application/json",
        "api-key": SEARCH_API_KEY,
    }
    payload = {
        "search": question,
        "top": SEARCH_TOP_K,
        "queryType": "semantic",
        "semanticConfiguration": SEARCH_SEMANTIC_CONFIG,
        "select": "key,commentsText,combinedText,fields",
        "vectorQueries": [
            {
                "kind": "text",
                "text": question,
                "fields": "combinedVector",
                "k": SEARCH_TOP_K,
            }
        ],
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def ask_openai(question: str, context_text: str) -> str:
    url = f"{AOAI_ENDPOINT}/openai/deployments/{AOAI_CHAT_DEPLOYMENT}/chat/completions?api-version={AOAI_API_VERSION}"
    headers = {
        "Content-Type": "application/json",
        "api-key": AOAI_API_KEY,
    }
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are a backlog analysis assistant. Answer only from the retrieved Jira context. Be concise and mention issue keys where useful."
            },
            {
                "role": "user",
                "content": f"Question:\\n{question}\\n\\nRetrieved Jira context:\\n{context_text}"
            }
        ],
        "temperature": 0.2,
        "max_tokens": 800,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


@app.post("/api/ask")
def ask(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    search_json = search_backlog(req.question)
    docs = search_json.get("value", [])

    if not docs:
        return {"answer": "I couldn't find any matching backlog items.", "results": []}

    blocks: List[str] = []
    results: List[Dict[str, Any]] = []

    for doc in docs:
        key = doc.get("key", "")
        fields = doc.get("fields") or {}
        summary = fields.get("summary", "")
        description = fields.get("description", "")
        comments_text = doc.get("commentsText", "")
        combined_text = doc.get("combinedText", "")

        results.append({
            "key": key,
            "summary": summary,
        })

        blocks.append(
            f"Key: {key}\n"
            f"Summary: {summary}\n"
            f"Description: {description}\n"
            f"Comments: {comments_text}\n"
            f"CombinedText: {combined_text}\n"
        )

    answer = ask_openai(req.question, "\n\n---\n\n".join(blocks))
    return {"answer": answer, "results": results}