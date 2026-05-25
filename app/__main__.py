"""Run the API directly: `python -m app`.

Binds to the PORT environment variable (assigned by the preview manager when
autoPort is enabled), defaulting to 8000. This is why the launch config carries
no hardcoded --port flag.
"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )
