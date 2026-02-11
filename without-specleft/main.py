"""FastAPI application for document approval workflow."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Document Approval Workflow API",
    description="Multi-step document approval workflow with delegation and escalation",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
