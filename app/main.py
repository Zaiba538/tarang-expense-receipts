
"""FastAPI application for Tarang Pharma expense receipt decisions."""

import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.decision_engine import make_decision
from app.extraction import extract_receipt_fields


app = FastAPI(
    title="Tarang Pharma Expense Receipt API",
    description="Receipt extraction, validation and expense policy decisions.",
    version="1.1.0",
)


class DecisionRequest(BaseModel):
    claim: dict[str, Any] = Field(
        ...,
        description="Claim details, including claim_id, category and amount_claimed",
    )
    receipt: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted receipt fields",
    )
    employee: dict[str, Any] = Field(
        default_factory=dict,
        description="Employee information relevant to policy checks",
    )
    receipt_available: bool = True
    duplicate_info: dict[str, Any] = Field(default_factory=dict)


@app.get("/")
def root() -> dict[str, str]:
    """Return basic API information."""
    return {
        "message": "Tarang Pharma Expense Receipt API",
        "docs": "/docs",
        "health": "/health",
        "photo_review": "/review",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    """Check whether the API is running."""
    return {"status": "ok"}


@app.post("/decide")
def decide_claim(request: DecisionRequest) -> dict[str, Any]:
    """Evaluate a claim using supplied receipt fields."""
    return make_decision(
        claim=request.claim,
        receipt=request.receipt,
        employee=request.employee,
        receipt_available=request.receipt_available,
        duplicate_info=request.duplicate_info,
    )


@app.post("/review")
async def review_receipt_photo(
    photo: UploadFile = File(..., description="Receipt image"),
    claim_id: str = Form(...),
    employee_id: str = Form(...),
    category: str = Form(...),
    amount_claimed: float = Form(...),
    receipt_date: str = Form(default=""),
) -> dict[str, Any]:
    """Extract receipt fields from an uploaded photo and evaluate the claim."""

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if photo.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPG, PNG, or WEBP receipt image.",
        )

    content = await photo.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")

    # Limit uploads to 10 MB.
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="The image exceeds the 10 MB upload limit.",
        )

    suffix = Path(photo.filename or "receipt.jpg").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=suffix, delete=False
        ) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            receipt = extract_receipt_fields(temp_path)
        except Exception as exc:
            # A failed OCR attempt should result in review, not a false rejection.
            receipt = {
                "vendor": "",
                "receipt_date": "",
                "receipt_number": "",
                "gstin": "",
                "total_amount": None,
                "vehicle_no": "",
                "readable": False,
                "errors": [f"Receipt extraction failed: {type(exc).__name__}"],
            }

        claim = {
            "claim_id": claim_id.strip(),
            "employee_id": employee_id.strip(),
            "category": category.strip(),
            "amount_claimed": amount_claimed,
        }
        if receipt_date.strip():
            claim["receipt_date"] = receipt_date.strip()

        employee: dict[str, Any] = {}
        employee_file = Path("data/Task 2 Files/employees.csv")
        if employee_file.exists():
            try:
                import pandas as pd

                employees = pd.read_csv(employee_file, dtype=str).fillna("")
                if "emp_id" in employees.columns:
                    matches = employees[
                        employees["emp_id"].str.strip().str.casefold()
                        == employee_id.strip().casefold()
                    ]
                    if not matches.empty:
                        employee = matches.iloc[0].to_dict()
            except Exception:
                # Continue with explicit limitations if employee lookup fails.
                employee = {}

        result = make_decision(
            claim=claim,
            receipt=receipt,
            employee=employee,
            receipt_available=True,
            duplicate_info={},
        )

        return {
            **result,
            "claim": claim,
            "receipt": receipt,
            "employee_found": bool(employee),
            "limitations": [
                "Cross-claim duplicate detection is not performed by this endpoint.",
                "Field-day and outstation eligibility may require manual verification.",
            ],
        }

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        await photo.close()
