import sys

import uvicorn

from app.config import LocalCallbackError, Settings

settings = Settings()
try:
    settings.check_local_callback()
except LocalCallbackError as error:
    sys.exit(str(error))
uvicorn.run(
    "app.main:app",
    host=settings.host,
    port=settings.port,
    reload=settings.reload,
    ssl_certfile=settings.ssl_certfile,
    ssl_keyfile=settings.ssl_keyfile,
)
