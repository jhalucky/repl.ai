from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_session
from app.gmail.oauth import router as gmail_oauth_router
from app.web.routes import router as web_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    scheduler = None
    if get_settings().enable_scheduler:
        from app.jobs.scheduler import start_scheduler

        scheduler = start_scheduler()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(title="repl.ai", lifespan=lifespan)
app.include_router(web_router)
app.include_router(gmail_oauth_router)


@app.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok"}
