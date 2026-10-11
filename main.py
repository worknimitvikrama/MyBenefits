"""
Eligibility-checker tool endpoint for the Writer AI Studio agent.

Run locally:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Then expose it publicly for Writer AI Studio's Agent Builder to call
(Writer's tool-calling needs a public HTTPS URL, not localhost):
    ngrok http 8000
and paste the ngrok URL + /check-eligibility into the Custom Tool config
using data/tool_schema.json as the function schema.

For anything beyond a live demo, deploy this instead to Render/Fly.io/Railway
so the URL is stable.
"""

from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, List

from rules import RULES

app = FastAPI(title="Benefits Eligibility Checker")


class EligibilityRequest(BaseModel):
    household_size: int = Field(..., ge=1)
    monthly_household_income: float = Field(..., ge=0)
    state: Optional[str] = None
    ages: Optional[List[int]] = None
    has_children_under_5: bool = False
    is_pregnant_or_postpartum: bool = False
    has_disability: bool = False
    is_65_or_older: bool = False
    employment_status: str = "unknown"
    already_enrolled_programs: Optional[List[str]] = None


@app.post("/check-eligibility")
def check_eligibility(req: EligibilityRequest):
    """Runs every program rule against the household profile and returns a
    checklist-style result. This is the function the Writer agent should
    call as a tool — see data/tool_schema.json for the schema to register."""
    kwargs = req.dict()
    income = kwargs.pop("monthly_household_income")
    household_size = kwargs.pop("household_size")

    results = []
    for program_id, rule_fn in RULES.items():
        results.append(rule_fn(income=income, household_size=household_size, **kwargs))

    return {
        "household_size": household_size,
        "monthly_household_income": income,
        "results": results,
    }


@app.get("/health")
def health():
    return {"status": "ok"}
