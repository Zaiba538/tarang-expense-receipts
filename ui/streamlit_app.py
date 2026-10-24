"""Streamlit UI for Tarang Pharma expense receipt review."""

import csv
import hashlib
import sys
import tempfile
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="Tarang Pharma | Receipt Review",
    page_icon="🧾",
    layout="wide",
)

st.title("Tarang Pharma — Expense Receipt Review")
st.caption("OCR-assisted receipt extraction and policy checks")

st.info(
    "This is a decision-support prototype. Verify the original receipt "
    "and supporting policy evidence before payment. Uncertain claims "
    "should be reviewed by a person."
)

with st.sidebar:
    st.header("How to use")
    st.write("1. Upload a receipt.")
    st.write("2. Enter the claim details.")
    st.write("3. Extract and verify the receipt fields.")
    st.write("4. Evaluate the claim.")
    st.warning(
        "An amount below ₹2,000 does not automatically make a claim eligible."
    )


# Editable receipt fields: (label, receipt key). Each widget key is edit_<key>.
RECEIPT_FIELDS = [
    ("Vendor", "vendor"),
    ("Receipt date", "receipt_date"),
    ("Receipt number", "receipt_number"),
    ("GSTIN", "gstin"),
    ("Total amount", "total_amount"),
    ("Vehicle number", "vehicle_no"),
]


def load_employee(emp_id: str) -> dict:
    """Find an employee by ID in the supplied employees.csv file."""
    employee_file = ROOT / "data" / "Task 2 Files" / "employees.csv"

    if not emp_id.strip():
        return {}

    if not employee_file.exists():
        st.warning(
            "employees.csv was not found. Employee-dependent checks "
            "will require manual review."
        )
        return {}

    try:
        with employee_file.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)

            for row in reader:
                if (
                    (row.get("emp_id") or "").strip().casefold()
                    == emp_id.strip().casefold()
                ):
                    return {
                        key: (value or "").strip()
                        for key, value in row.items()
                    }
    except (OSError, csv.Error) as exc:
        st.warning(f"Could not read employee records: {exc}")
        return {}

    return {}


uploaded_file = st.file_uploader(
    "Upload a receipt photo",
    type=["jpg", "jpeg", "png", "webp", "bmp"],
)

# Results belong to one image. When the uploaded image changes (by content,
# not by name) or is removed, drop the previous receipt's extraction, edits
# and decision so they are never shown against a different photo.
RECEIPT_STATE_KEYS = (
    "receipt", "claim", "receipt_editor_values", "edited_receipt",
    "last_result", "last_final_receipt", "last_employee",
)
current_image_hash = (
    hashlib.sha256(uploaded_file.getvalue()).hexdigest() if uploaded_file else None
)
if st.session_state.get("receipt_image_hash") != current_image_hash:
    for state_key in RECEIPT_STATE_KEYS:
        st.session_state.pop(state_key, None)
    for _, field_key in RECEIPT_FIELDS:
        st.session_state.pop(f"edit_{field_key}", None)
    st.session_state["receipt_image_hash"] = current_image_hash

left, right = st.columns(2)

with left:
    st.subheader("Claim details")
    claim_id = st.text_input("Claim ID", placeholder="e.g. CLM-31086")
    emp_id = st.text_input("Employee ID", placeholder="e.g. TPD-0412")

    category = st.selectbox(
        "Expense category",
        ["Fuel", "Food", "Local travel", "Courier", "Parking", "Lodging"],
    )

    amount_text = st.text_input(
        "Claimed amount (₹)",
        placeholder="e.g. 300.00",
    )

    expense_date = st.text_input(
        "Expense date (optional)",
        placeholder="YYYY-MM-DD",
    )

with right:
    st.subheader("Receipt preview")
    if uploaded_file:
        st.image(
            uploaded_file.getvalue(),
            caption=uploaded_file.name,
            use_container_width=True,
        )
    else:
        st.write("Upload an image to preview it here.")


if st.button("Extract receipt fields", type="primary"):
    if uploaded_file is None:
        st.error("Upload a receipt image first.")
        st.stop()

    if not claim_id.strip():
        st.error("Enter a claim ID.")
        st.stop()

    if not emp_id.strip():
        st.error("Enter an Employee ID.")
        st.stop()

    if not amount_text.strip():
        st.error("Enter the claimed amount.")
        st.stop()

    try:
        amount = float(
            amount_text.replace(",", "").replace("₹", "").strip()
        )
        if amount < 0:
            raise ValueError
    except ValueError:
        st.error("Enter a valid, non-negative claimed amount.")
        st.stop()

    try:
        from app.extraction import extract_receipt_fields
    except Exception as exc:
        st.error("The receipt extraction module could not be loaded.")
        st.caption(f"{type(exc).__name__}: {exc}")
        st.stop()

    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        suffix = ".jpg"

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp:
            temp.write(uploaded_file.getvalue())
            temp_path = Path(temp.name)

        with st.spinner("Extracting receipt fields with OCR..."):
            receipt = extract_receipt_fields(temp_path)

        st.session_state["receipt"] = receipt
        st.session_state["claim"] = {
            "claim_id": claim_id.strip(),
            "emp_id": emp_id.strip(),
            "category": category,
            "amount_claimed": amount,
            "expense_date": expense_date.strip(),
        }

        # A new extraction invalidates the previous decision.
        st.session_state.pop("last_result", None)

        # It also replaces the editable fields. The text inputs keep their
        # own state by key, so clear those too or they show the old receipt.
        st.session_state["receipt_editor_values"] = {
            key: "" if receipt.get(key) is None else str(receipt.get(key))
            for _, key in RECEIPT_FIELDS
        }
        for _, key in RECEIPT_FIELDS:
            st.session_state.pop(f"edit_{key}", None)

    except Exception as exc:
        st.error("Receipt processing failed. Check the image and OCR installation.")
        st.caption(f"{type(exc).__name__}: {exc}")

    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


if "receipt" in st.session_state and "claim" in st.session_state:
    st.divider()
    st.header("Verify extracted receipt fields")
    st.caption(
        "OCR values are editable. Correct any mistakes using the original receipt."
    )

    receipt = st.session_state["receipt"]

    # Use extracted values as editable defaults.
    # The key keeps reviewer edits available across Streamlit reruns.
    if "receipt_editor_values" not in st.session_state:
        st.session_state["receipt_editor_values"] = {
            key: "" if receipt.get(key) is None else str(receipt.get(key, ""))
            for _, key in RECEIPT_FIELDS
        }

    edited_receipt = {}
    columns = st.columns(2)

    for index, (label, key) in enumerate(RECEIPT_FIELDS):
        current_value = st.session_state["receipt_editor_values"].get(key, "")

        edited_receipt[key] = columns[index % 2].text_input(
            label,
            value=current_value,
            key=f"edit_{key}",
        )

    # Preserve extraction metadata needed by the decision engine.
    for key in (
        "raw_text",
        "readable",
        "errors",
    ):
        edited_receipt[key] = receipt.get(key)

    st.session_state["edited_receipt"] = edited_receipt

    st.caption(
        "Only correct values that you can verify from the receipt. "
        "Leave unreadable or unknown fields blank."
    )

    if st.button("Evaluate claim", type="primary"):
        try:
            from app.decision_engine import make_decision

            claim = dict(st.session_state["claim"])
            employee = load_employee(claim.get("emp_id", ""))

            if not employee:
                st.warning(
                    "Employee record was not found. The claim should remain "
                    "under review until the employee details are verified."
                )

            # Use the reviewer's corrected values, not the original OCR values.
            final_receipt = dict(st.session_state["edited_receipt"])

            # Convert the corrected receipt amount to a number when possible.
            raw_total = str(final_receipt.get("total_amount") or "").strip()
            if raw_total:
                try:
                    final_receipt["total_amount"] = float(
                        raw_total.replace(",", "")
                        .replace("₹", "")
                        .strip()
                    )
                except ValueError:
                    st.error(
                        "Enter a valid number in Total amount, or leave it blank "
                        "if the amount cannot be read."
                    )
                    st.stop()
            else:
                final_receipt["total_amount"] = None

            with st.spinner("Evaluating policy checks..."):
                result = make_decision(
                    claim=claim,
                    receipt=final_receipt,
                    employee=employee,
                    receipt_available=True,
                    duplicate_info={
                        "duplicate_detected": False,
                        "possible_matches": [],
                    },
                )

            st.session_state["last_result"] = result
            st.session_state["last_final_receipt"] = final_receipt
            st.session_state["last_employee"] = employee

        except Exception as exc:
            st.error("Claim evaluation failed.")
            st.caption(f"{type(exc).__name__}: {exc}")


if "last_result" in st.session_state:
    result = st.session_state["last_result"]

    st.divider()
    st.header("Review result")

    if str(result.get("decision", "review")).lower() == "approve":
        st.success("Recommended decision: APPROVE")
    else:
        st.warning("Recommended decision: REVIEW")

    st.write("**Reason:**", result.get("reason", "Manual review required."))

    reasons = result.get("reasons", [])
    if reasons:
        st.subheader("Checks requiring attention")
        for reason in reasons:
            st.write(f"- {reason}")

    employee = st.session_state.get("last_employee", {})
    if not employee:
        st.warning(
            "Employee details could not be verified. Do not treat this claim "
            "as ready for payment."
        )
    else:
        st.caption(
            f"Employee record found: {employee.get('name', 'Name unavailable')} "
            f"({employee.get('emp_id', '')})."
        )

    errors = st.session_state.get("last_final_receipt", {}).get("errors", [])
    if errors:
        st.subheader("Extraction warnings")
        for error in errors:
            st.write(f"- {error}")

    st.caption(
        "The prototype does not independently establish field-day eligibility "
        "or cross-claim duplicates. Verify those separately before payment. "
        "A missing field or possible duplicate is not proof of fraud."
    )

