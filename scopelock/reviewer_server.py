"""Uvicorn entrypoint for the public reviewer gateway."""

import os

import uvicorn

from scopelock.reviewer_gateway import app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
