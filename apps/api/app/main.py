from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.db.session import Base, engine
from app.models import File, Job, PageResult, StructuredResult, User  # noqa: F401


def create_app() -> FastAPI:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
