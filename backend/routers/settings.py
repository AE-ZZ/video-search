from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend import config

router = APIRouter(tags=["settings"])


class SettingsResponse(BaseModel):
    video_library_path: str


class SetLibraryRequest(BaseModel):
    video_library_path: str


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    return SettingsResponse(video_library_path=config.VIDEO_LIBRARY_PATH)


@router.post("/settings", response_model=SettingsResponse)
async def update_settings(body: SetLibraryRequest, request: Request):
    library_path = body.video_library_path.strip()

    # Validate path exists
    if not Path(library_path).is_dir():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {library_path}")

    # Persist to .env file
    _update_env("VIDEO_LIBRARY_PATH", library_path)

    # Update in-memory config
    config.VIDEO_LIBRARY_PATH = library_path

    # Restart watcher and scan
    manager = request.app.state.library_manager
    _restart_watcher(request.app, library_path, manager)
    manager.initial_scan(library_path)

    return SettingsResponse(video_library_path=library_path)


def _update_env(key: str, value: str):
    """Update or add a key in the .env file."""
    env_path = config.ENV_FILE
    lines = []
    found = False

    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith(f"{key}="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)

    if not found:
        lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n")


def _restart_watcher(app, library_path: str, manager):
    """Stop old watcher and start a new one for the updated path."""
    from backend.services.watcher import start_watcher

    if hasattr(app.state, "watcher") and app.state.watcher:
        app.state.watcher.stop()
        app.state.watcher.join()

    app.state.watcher = start_watcher(
        library_path,
        process_callback=manager.process_file,
        remove_callback=manager.remove_file,
    )
