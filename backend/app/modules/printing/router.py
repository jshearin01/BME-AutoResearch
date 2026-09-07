"""Print prep: FOSS slicer profiles + checklist. Orca/Prusa CLI if installed."""

import json
import pathlib
import shutil
import subprocess
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/printing", tags=["printing"])

ROOT = pathlib.Path(__file__).resolve().parents[5]
PROFILES_DIR = ROOT / "printer-profiles"


def find_slicer() -> str | None:
    for cand in ["orcaslicer", "orca-slicer", "prusa-slicer", "prusaslicer", "slic3r", "curaengine"]:
        if shutil.which(cand):
            return cand
    # macOS app bundles
    for app in ["/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer",
                "/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"]:
        if pathlib.Path(app).exists():
            return app
    return None


@router.get("/profiles")
def profiles():
    if not PROFILES_DIR.exists():
        return {"profiles": [], "note": "printer-profiles/ missing"}
    detail = []
    for p in PROFILES_DIR.glob("*.json"):
        try:
            detail.append({"file": p.name, **json.loads(p.read_text())})
        except Exception:
            detail.append({"file": p.name})
    return {"profiles": [p.name for p in PROFILES_DIR.glob("*.json")],
            "detail": detail, "slicer_found": find_slicer()}


@router.post("/packet")
def packet(body: dict):
    # Returns slice-ready checklist; Orca/Prusa CLI wired in Phase 3.
    return {
        "project_id": body.get("project_id"),
        "stl_file": body.get("stl_file"),
        "slicer_found": find_slicer(),
        "recommended": {"slicer": "OrcaSlicer (FOSS)", "material": "PETG for wipe-clean parts",
                        "layer_mm": 0.2, "walls": 3, "infill": "20% gyroid",
                        "supports": "avoid if possible; orient flat"},
        "preflight": ["watertight STL", "min wall >=1.2mm (2mm for loaded parts)",
                      "no overhangs >60° without supports", "brim if footprint small",
                      "record filament lot + temp in print log"],
        "slice_cmd_hint": "orcaslicer --slice model.stl --load generic-petg.json --output out.3mf",
    }


@router.post("/slice")
def slice_model(body: dict):
    """Attempt CLI slice if a FOSS slicer is installed; else return manual hint."""
    stl = body.get("stl_file", "")
    p = pathlib.Path(stl)
    if not p.is_file():
        raise HTTPException(404, f"STL not found: {stl}")
    slicer = find_slicer()
    if not slicer:
        return {"sliced": False, "slicer_found": None,
                "hint": "Install OrcaSlicer (https://github.com/SoftFever/OrcaSlicer) then POST again. "
                        f"Manual: orcaslicer --slice {stl} --output print.3mf"}
    out = p.with_suffix(".3mf")
    # Best-effort: many slicers accept `--slice file --output out`
    # Prusa/Orca GUI binaries may ignore CLI flags — capture output either way.
    try:
        proc = subprocess.run([slicer, "--slice", str(p), "--output", str(out)],
                              capture_output=True, text=True, timeout=300)
        ok = out.exists()
        return {"sliced": ok, "slicer": slicer, "output": str(out) if ok else None,
                "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:],
                "returncode": proc.returncode}
    except Exception as e:
        return {"sliced": False, "slicer": slicer, "error": str(e)}
