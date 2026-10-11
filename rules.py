"""
Deterministic eligibility rules for the government-benefits navigator hackathon demo.

IMPORTANT — VERIFY BEFORE THE DEMO:
Federal Poverty Guidelines (FPL) change every January and some program rules
have exceptions this simplified engine does not model (asset tests, categorical
eligibility, state-specific variations, immigration-status carve-outs, etc.).
The numbers below are the 2024 HHS Federal Poverty Guidelines for the 48
contiguous states + DC, used here as an illustrative baseline so the demo has
real math behind it. Before presenting to judges, check
https://aspe.hhs.gov/poverty-guidelines for the current year's numbers and
swap FPL_BASE / FPL_INCREMENT below if they've changed.

Every rule function returns a dict with a `citation` field — the assistant's
final answer MUST surface that citation, per the "cites the official source
for every answer" requirement from the hackathon brief.
"""

from typing import Optional

# 2024 HHS Federal Poverty Guidelines, 48 contiguous states + DC (annual, USD).
FPL_BASE_1_PERSON = 15060
FPL_INCREMENT_PER_PERSON = 5380
FPL_SOURCE = "https://aspe.hhs.gov/poverty-guidelines"


def annual_fpl(household_size: int) -> float:
    size = max(household_size, 1)
    return FPL_BASE_1_PERSON + FPL_INCREMENT_PER_PERSON * (size - 1)


def monthly_fpl(household_size: int) -> float:
    return annual_fpl(household_size) / 12


def _pct_of_fpl(monthly_income: float, household_size: int) -> float:
    fpl = monthly_fpl(household_size)
    if fpl <= 0:
        return 0.0
    return (monthly_income / fpl) * 100


def check_snap(income: float, household_size: int, **_) -> dict:
    pct = _pct_of_fpl(income, household_size)
    eligible = pct <= 130
    return {
        "program": "SNAP",
        "eligible": eligible,
        "confidence": "likely" if eligible else "unlikely",
        "reason": f"Household gross monthly income is {pct:.0f}% of the Federal Poverty "
                  f"Level (limit is 130% for SNAP).",
        "citation": "https://www.fns.usda.gov/snap/recipient/eligibility",
    }


def check_medicaid(income: float, household_size: int, state: Optional[str] = None, **_) -> dict:
    pct = _pct_of_fpl(income, household_size)
    # 138% FPL is the ACA expansion threshold in expansion states; non-expansion
    # states use lower, categorical rules. We can't resolve per-state limits here.
    eligible_expansion_state = pct <= 138
    return {
        "program": "Medicaid",
        "eligible": eligible_expansion_state,
        "confidence": "needs_state_check",
        "reason": f"Household income is {pct:.0f}% of FPL. In Medicaid-expansion states the "
                  f"limit is generally 138% of FPL; non-expansion states and specific "
                  f"categories (pregnant, disabled, children) have different limits. "
                  f"State: {state or 'not provided'} — confirm against state Medicaid rules.",
        "citation": "https://www.medicaid.gov/medicaid/eligibility/index.html",
    }


def check_ssi(income: float, household_size: int, has_disability: bool = False,
               is_65_or_older: bool = False, **_) -> dict:
    # 2024 SSI federal benefit rate / income limit proxy for an individual.
    ssi_income_limit_individual = 1971  # approx "countable income" cutoff, illustrative
    per_person_income = income / max(household_size, 1)
    qualifies_category = has_disability or is_65_or_older
    eligible = qualifies_category and per_person_income <= ssi_income_limit_individual
    return {
        "program": "SSI",
        "eligible": eligible,
        "confidence": "likely" if eligible else (
            "not_eligible_category" if not qualifies_category else "unlikely"
        ),
        "reason": "SSI requires being 65+, blind, or disabled AND having limited income and "
                  "resources. " + (
                      "Category requirement met." if qualifies_category
                      else "No disability/age-65+ indicated, so SSI is unlikely to apply — "
                           "SSDI or other programs may fit better."
                  ),
        "citation": "https://www.ssa.gov/ssi/eligibility.htm",
    }


def check_liheap(income: float, household_size: int, **_) -> dict:
    pct = _pct_of_fpl(income, household_size)
    eligible = pct <= 150
    return {
        "program": "LIHEAP",
        "eligible": eligible,
        "confidence": "likely" if eligible else "unlikely",
        "reason": f"Household income is {pct:.0f}% of FPL (many states use a 150% FPL cap "
                  f"for LIHEAP, though some use area median income instead — confirm with "
                  f"your state's LIHEAP office).",
        "citation": "https://www.acf.hhs.gov/ocs/liheap-eligibility-criteria",
    }


def check_wic(income: float, household_size: int, is_pregnant_or_postpartum: bool = False,
              has_children_under_5: bool = False, already_enrolled_programs=None, **_) -> dict:
    already_enrolled_programs = already_enrolled_programs or []
    categorical = bool(set(p.lower() for p in already_enrolled_programs) & {"snap", "medicaid", "tanf"})
    pct = _pct_of_fpl(income, household_size)
    income_eligible = pct <= 185
    category_eligible = is_pregnant_or_postpartum or has_children_under_5
    eligible = category_eligible and (income_eligible or categorical)
    return {
        "program": "WIC",
        "eligible": eligible,
        "confidence": "likely" if eligible else "unlikely",
        "reason": (
            "WIC requires being pregnant/postpartum or having a child under 5, AND "
            f"income at or below 185% FPL (household is at {pct:.0f}%) OR already being "
            "enrolled in SNAP/Medicaid/TANF (automatic income eligibility)."
        ),
        "citation": "https://www.fns.usda.gov/wic/wic-eligibility-requirements",
    }


def check_eitc(income: float, household_size: int, employment_status: str = "unknown", **_) -> dict:
    # Rough 2024 EITC income ceilings by number of qualifying children (proxy from household size - 1).
    qualifying_children = max(household_size - 1, 0)
    annual_income = income * 12
    ceilings = {0: 18591, 1: 49084, 2: 55768, 3: 59899}
    ceiling = ceilings.get(min(qualifying_children, 3), ceilings[3])
    has_earned_income = employment_status in ("employed", "self_employed")
    eligible = has_earned_income and annual_income <= ceiling
    return {
        "program": "EITC",
        "eligible": eligible,
        "confidence": "likely" if eligible else "unlikely",
        "reason": f"Estimated annual income ${annual_income:,.0f} vs. approx. IRS ceiling "
                  f"${ceiling:,.0f} for {qualifying_children} qualifying children. Requires "
                  f"earned income (employed/self-employed).",
        "citation": "https://www.irs.gov/credits-deductions/individuals/earned-income-tax-credit-eitc",
    }


def check_section8(income: float, household_size: int, **_) -> dict:
    # Real HUD income limits are county-specific (% of Area Median Income, not FPL).
    # This is a rough national proxy only — flagged clearly to the user.
    pct = _pct_of_fpl(income, household_size)
    eligible = pct <= 200  # rough stand-in; real limit is ~80% of local AMI
    return {
        "program": "Housing Choice Voucher (Section 8)",
        "eligible": eligible,
        "confidence": "rough_estimate_verify_locally",
        "reason": (
            "HUD income limits are based on your local Area Median Income (AMI), not the "
            "national poverty line, and vary by county. This is only a rough national "
            f"estimate ({pct:.0f}% of FPL); contact your local Public Housing Agency for "
            "the exact limit and waitlist status."
        ),
        "citation": "https://www.hud.gov/topics/housing_choice_voucher_program_section_8",
    }


RULES = {
    "snap": check_snap,
    "medicaid": check_medicaid,
    "ssi": check_ssi,
    "liheap": check_liheap,
    "wic": check_wic,
    "eitc": check_eitc,
    "section8": check_section8,
}
