"""Print prep: FOSS slicer profiles + checklist. No printer touched in v0."""

import pathlib
from fastapi import APIRouter

router = APIRouter(prefix="/api/printing", tags=["printing"])

ROOT = pathlib.Path(__file__).resolve().parents[5]
PROFILES_DIR = ROOT / "printer-profiles"


@router.get("/profiles")
def profiles():
    if not PROFILES_DIR.exists():
        return {"profiles": [], "note": "printer-profiles/ missing"}
    return {"profiles": [p.name for p in PROFILES_DIR.glob("*.json")]}


@router.post("/packet")
def packet(body: dict):
    # Returns slice-ready checklist; Orca/Prusa CLI wired in Phase 3.
    return {
        "project_id": body.get("project_id"),
        "stl_file": body.get("stl_file"),
        "recommended": {"slicer": "OrcaSlicer (FOSS)", "material": "PETG for wipe-clean parts",
                        "layer_mm": 0.2, "walls": 3, "infill": "20% gyroid",
                        "supports": "avoid if possible; orient flat"},
        "preflight": ["watertight STL", "min wall >=1.2mm (2mm for loaded parts)",
                      "no overhangs >60° without supports", "brim if footprint small",
                      "record filament lot + temp in print log"],
        "slice_cmd_hint": "orcaslicer --slice model.stl --load generic-petg.json --output out.3mf",
    }
