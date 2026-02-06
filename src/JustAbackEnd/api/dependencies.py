from fastapi import Request
from JustAbackEnd.core.settings import Settings
from JustAbackEnd.core.runtime import AppRuntime


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_app_runtime(request: Request) -> AppRuntime:
    return request.app.state.runtime
