from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.database import init_db
from app.routes import router
from app.services import ServiceError

app = FastAPI(title="Document Approval API", version="0.1.0")

app.include_router(router, prefix="/api")


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.on_event("startup")
def on_startup():
    init_db()
