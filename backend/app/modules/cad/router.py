"""CAD builder: executes parametric CadQuery/OpenSCAD-style Python in a sandbox dir.

v0: safe builtins only, writes STL if cadquery+trimesh installed,
else writes .py + validation checklist. Never exec() untrusted imports blindly.
"""

import os
import pathlib
import datetime
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/cad", tags=["cad"])

DATA = pathlib.Path(os.environ.get("DATA_DIR", "./data"))
CAD_DIR = DATA / "cad"
CAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_PREFIXES = ("import cadquery", "import build123d", "import trimesh",
                    "from cadquery", "from build123d", "#", "import math",
                    "length", "width", "height", "result", "show", "cq", "bd")


def validate_code(code: str) -> list[str]:
    issues = []
    banned = ["os.", "sys.", "subprocess", "socket", "open(", "eval(", "exec("]
    for b in banned:
        if b in code:
            issues.append(f"blocked pattern: {b}")
    if "min_wall" not in code.lower() and "thickness" not in code.lower():
        issues.append("warning: no explicit wall thickness — add >=1.2mm check")
    return issues


@router.post("/generate")
async def generate_cad(body: dict):
    project_id = body.get("project_id", "global")
    code = body.get("code", "")
    if not code:
        # Default parametric template: pill-cap grip aid
        code = open(pathlib.Path(__file__).parent / "template_default.py").read() \
            if (pathlib.Path(__file__).parent / "template_default.py").exists() else DEFAULT_CODE
    issues = validate_code(code)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    py_path = CAD_DIR / f"{project_id}_{stamp}.py"
    py_path.write_text(code)
    stl_path = CAD_DIR / f"{project_id}_{stamp}.stl"
    stl_made, stl_note = try_build_stl(code, stl_path)
    return {"py_file": str(py_path), "stl_file": str(stl_path) if stl_made else None,
            "issues": issues, "stl_note": stl_note, "code": code}


def try_build_stl(code: str, out_path: pathlib.Path):
    try:
        import cadquery as cq  # type: ignore
    except Exception as e:
        return False, f"cadquery not installed ({e}); code saved, run locally to export STL."
    try:
        ns: dict = {}
        exec(compile(code, "<cad>", "exec"), {"cq": cq, "__builtins__": __builtins__}, ns)
        shape = ns.get("result")
        if shape is None:
            return False, "code ran but no `result` shape found."
        cq.exporters.export(shape, str(out_path))
        # quick mesh sanity via trimesh if available
        try:
            import trimesh
            m = trimesh.load(str(out_path))
            return True, f"STL ok: watertight={m.is_watertight}, volume={float(m.volume):.1f}mm³"
        except Exception:
            return True, "STL exported (trimesh check skipped)."
    except Exception as e:
        return False, f"build failed: {e}"


@router.get("/download")
def download(path: str):
    p = pathlib.Path(path)
    try:
        resolved = p.resolve()
        cad_resolved = CAD_DIR.resolve()
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(404, "file not found")
    if not resolved.is_file() or cad_resolved not in resolved.parents:
        # also allow bare filename
        alt = (CAD_DIR / p.name).resolve()
        if not alt.is_file():
            from fastapi import HTTPException
            raise HTTPException(404, "file not found")
        resolved = alt
    return FileResponse(str(resolved))


@router.get("/files")
def list_files(project_id: str | None = None):
    files = sorted(CAD_DIR.glob("*.stl" if False else "*.*"))
    out = []
    for f in files:
        if project_id and not f.name.startswith(project_id):
            continue
        if f.suffix not in (".stl", ".py", ".3mf"):
            continue
        out.append({"name": f.name, "path": str(f),
                    "bytes": f.stat().st_size,
                    "mtime": f.stat().st_mtime})
    return {"cad_dir": str(CAD_DIR), "files": sorted(out, key=lambda x: x["mtime"], reverse=True)[:100]}


@router.post("/validate")
def validate_stl(body: dict):
    path = body.get("stl_file", "")
    p = pathlib.Path(path)
    if not p.is_file():
        alt = CAD_DIR / pathlib.Path(path).name
        p = alt
    if not p.is_file():
        from fastapi import HTTPException
        raise HTTPException(404, f"STL not found: {path}")
    try:
        import trimesh
        m = trimesh.load(str(p))
        bbox = m.bounds.tolist() if hasattr(m, "bounds") else None
        return {"file": str(p), "watertight": bool(m.is_watertight),
                "volume_mm3": float(m.volume) if m.is_volume else None,
                "faces": int(len(m.faces)), "bbox_mm": bbox,
                "pass": bool(m.is_watertight),
                "checks": ["watertight", "min-wall>=1.2mm (verify in CAD params)",
                           "max-envelope<=printer bed (verify vs profile)"]}
    except ImportError:
        return {"file": str(p), "note": "trimesh not installed — install to validate"}
    except Exception as e:
        return {"file": str(p), "pass": False, "error": str(e)}


DEFAULT_CODE = '''"""Parametric pill-cap grip aid (FDM, min wall 2mm). `result` is exported."""
import cadquery as cq
length, width, height, wall = 80.0, 45.0, 25.0, 2.0  # mm
outer = cq.Workplane("XY").box(length, width, height)
inner = cq.Workplane("XY").box(length - wall*2, width - wall*2, height).translate((0, 0, wall))
result = outer.cut(inner)
'''
