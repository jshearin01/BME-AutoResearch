"""Safety critic: rule-based flags + LLM review. Gate before print."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.shared.db import get_db
from app.shared.observability import log_run
from app.shared.llm import generate

router = APIRouter(prefix="/api/safety", tags=["safety"])

HIGH_RISK = ["implant", "invasive", "sterile", "catheter", "surgical", "diagnos",
             "dosage", "dose", "injection", "wound", "blood", "airway", "ventilator"]


@router.post("/check")
async def check(body: dict, db: Session = Depends(get_db)):
    text = (body.get("title", "") + " " + body.get("problem", "") + " " + body.get("spec", ""))
    flags = sorted({w for w in HIGH_RISK if w in text.lower()})
    verdict = "BLOCKED — human review required" if flags else "PASS with disclaimer"
    prompt = (f"Design text: {text[:2500]}\nFlags: {flags}\n"
              "Output: risk class, biocompat/cleaning concerns, what must be verified "
              "before printing/handling, and a one-line safe-use disclaimer.")
    review = await generate(prompt)
    log_run(db, body.get("project_id"), "safety", "safety.check", f"{text[:300]} || {prompt[:1500]}", f"{verdict} || {review[:2000]}")
    return {"verdict": verdict, "flags": flags, "review": review, "prompt": prompt,
            "disclaimer": "Research prototype only. Not a medical device. No clinical use."}
