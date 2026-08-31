"""FastAPI エントリポイント。"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="labyrinth-of-time")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
