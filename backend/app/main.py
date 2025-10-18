from api.routes_health import router as health_router
from api.routes_horoscope import router as horoscope_router
from core.container import container
from core.logging import setup_logging
from fastapi import FastAPI
from middlewares.request_id import RequestIDMiddleware
from middlewares.timing import TimingMiddleware


def create_app() -> FastAPI:
    setup_logging()
    settings = container.settings
    app = FastAPI(title=settings.APP_NAME, debug=settings.APP_DEBUG)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TimingMiddleware)
    app.include_router(health_router)
    app.include_router(horoscope_router)
    return app


app = create_app()

