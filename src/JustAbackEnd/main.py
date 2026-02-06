import uvicorn
from JustAbackEnd.core.constants import HOST, LOCAL_DEV_PORT
from JustAbackEnd.bootstrap.app_factory import create_app

def run_app():
    return create_app()

def run_app_locally():
    uvicorn.run(
        "JustAbackEnd.bootstrap.app_factory:create_app",
        host=HOST,
        port=LOCAL_DEV_PORT,
        reload=True,
        factory=True,
        log_config=None,
    )


if __name__ == "__main__":
    run_app_locally()
