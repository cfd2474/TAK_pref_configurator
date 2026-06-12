"""TAK-CIV Preference Configurator API."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .pref_generator import DEFAULT_APP_PREFS, generate_pref_xml
from .pref_parser import parse_pref_xml
from .secrets import redact_preferences
from .validation import validate_connections

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR.parent / "data"
SCHEMA_PATH = DATA_DIR / "preference_schema.json"
FRONTEND_DIR = APP_DIR.parent.parent / "frontend"

app = FastAPI(
    title="TAK-CIV Preference Configurator",
    description="Web tool for creating TAK-CIV .pref configuration files",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PreferenceValue(BaseModel):
    type: str = "string"
    value: str | bool | int | float | list[str] | None = None
    java_class: str | None = None


class GenerateRequest(BaseModel):
    filename: str = Field(default="tak-civ-config.pref", pattern=r"^[\w.\-]+$")
    preference_name: str = DEFAULT_APP_PREFS
    include_empty_connection_groups: bool = True
    connections: dict[str, list[dict]] = Field(default_factory=dict)
    preferences: dict[str, PreferenceValue] = Field(default_factory=dict)


def load_schema() -> dict:
    if not SCHEMA_PATH.exists():
        raise HTTPException(status_code=500, detail="Preference schema not found")
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/schema")
def get_schema() -> dict:
    return load_schema()


@app.post("/api/generate")
def generate_pref(request: GenerateRequest) -> Response:
    connection_errors = validate_connections(request.connections)
    if connection_errors:
        raise HTTPException(status_code=400, detail="; ".join(connection_errors))

    config = {
        "preference_name": request.preference_name,
        "include_empty_connection_groups": request.include_empty_connection_groups,
        "connections": request.connections,
        "preferences": {
            key: pref.model_dump(exclude_none=True)
            for key, pref in request.preferences.items()
            if pref.value is not None and pref.value != ""
        },
    }
    config["preferences"] = redact_preferences(config["preferences"])
    xml_content = generate_pref_xml(config)
    filename = request.filename if request.filename.endswith(".pref") else f"{request.filename}.pref"
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/parse")
async def parse_pref(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith((".pref", ".xml")):
        raise HTTPException(status_code=400, detail="Upload a .pref or .xml file")
    content = (await file.read()).decode("utf-8", errors="replace")
    try:
        parsed = parse_pref_xml(content)
        parsed["preferences"] = redact_preferences(parsed["preferences"])
        return parsed
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse preference file: {exc}") from exc


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
