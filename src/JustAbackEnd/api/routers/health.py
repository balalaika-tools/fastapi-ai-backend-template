import sys
import platform
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import ORJSONResponse
from JustAbackEnd.api.schemas import HealthResponse
from JustAbackEnd.core.constants import API_VERSION

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", response_class=ORJSONResponse)
async def liveness():
    return {"status": "alive"}


@router.get("/ready", response_class=ORJSONResponse)
async def readiness(request: Request):
    runtime = request.app.state.runtime
    checks = {"llm_model": runtime._model is not None}
    all_ready = all(checks.values())
    return ORJSONResponse(
        status_code=200 if all_ready else 503,
        content={"status": "ready" if all_ready else "not_ready", "checks": checks},
    )


@router.get("", response_model=HealthResponse, response_class=ORJSONResponse)
async def health(request: Request):
    runtime = request.app.state.runtime
    services = {"llm_model": runtime._model is not None}
    return HealthResponse(
        status="healthy" if all(services.values()) else "degraded",
        timestamp=datetime.now(timezone.utc),
        version=API_VERSION,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        services=services,
    )
