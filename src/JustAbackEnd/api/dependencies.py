from typing import cast

from fastapi import Request

from JustAbackEnd.core.runtime import AppRuntime
from JustAbackEnd.core.settings import Settings


def get_settings_dep(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_app_runtime(request: Request) -> AppRuntime:
    return cast(AppRuntime, request.app.state.runtime)
