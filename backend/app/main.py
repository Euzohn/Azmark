import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.request_context import RequestContextMiddleware
from app.mcp.server import MCPMount
from app.services.admin import bootstrap_admin_from_env


def create_app() -> FastAPI:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # spec #85: MCP shares the api process; MCP_ENABLED=false removes the route.
    mcp_mount = MCPMount() if settings.mcp_enabled else None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # spec #78: create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD.
        # No-op unless both are configured and no active admin exists.
        bootstrap_admin_from_env()
        if mcp_mount is None:
            yield
            return
        # The MCP session manager can only be started once, so it lives here.
        async with mcp_mount.run():
            yield

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    # Stamps a correlation id on every request so audit rows can be grouped (#47).
    # Wraps both REST routes and the MCP mount.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    if mcp_mount is not None:
        # Raw ASGI mount: the MCP transport authenticates its own Bearer token.
        app.mount(f"{settings.api_v1_prefix}/mcp", mcp_mount)
    return app


app = create_app()
