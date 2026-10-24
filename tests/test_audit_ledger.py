
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.build_audit_ledger import (
    CONFIRMED,
    LEAD,
    POLICY,
    PAYER_OWNER_ON_PHOTO,
    PAYER_UNKNOWN,
    PAYER_VEHICLE_OWNER,
    PROBABLE,
    RETAINED,
    UNRESOLVED,
    build_ledger,
    load_project_inputs,
    summarize,
)


ALTERED_TEXT = (
    "SPICE ROUTE KITCHEN\nTAX INVOICE\nBill No: 6423\nSub Total\n190.00\n"
    "CGST @2.5%\n4.75\nSGST @2.5%\n4.75\nRound Off\n+0.50\nGRAND TOTAL\nRs\n1200.00"
)


def claim(claim_id, amount, emp="E1", category="Food", split="test", submitted="2026-07-01", status=""):
    return {
        "claim_id": claim_id, "emp_id": emp, "category": category,
        "amount_claimed": amount, "split": split, "submitted_on": submitted,
        "status": status,
    }


def receipt(claim_id, total, prefix="001", text="", number="", image_hash="", vendor="V"):
    return {
        "image_filename": f"{prefix}_{claim_id}.jpg", "vendor": vendor,
        "receipt_number": number, "receipt_date": "2026-07-01",
        "total_amount": total, "raw_text": text, "vehicle_no": "",
        "readable": "True", "image_sha256": image_hash,
    }


def photo(claim_id, kind, confidence="confirmed", amount="", supported="", prefix="001", related="", retained=""):
    return {
        "claim_id": claim_id, "image_prefix": prefix, "recorded_amount_claimed": amount,
        "finding_type": kind, "confidence": confidence, "photo_supported_amount": supported,
        "related_claim_ids": related, "retained_claim_id": retained, "evidence": "test evidence",
    }


def rows_for(rows, claim_id):
    return [row for row in rows if row["claim_id"] == claim_id]


def counted(rows):
    return [row for row in rows if row["counted_in_totals"]]


def test_categories_are_kept_separate():
    claims = [
        claim("A", "1200"), claim("B", "1180", emp="E2"),
        claim("C", "1200", emp="E3"), claim("D", "300", emp="E4", category="Fuel"),
    ]
    receipts = {
        "A": receipt("A", "1200", "001"), "B": receipt("B", "1180", "002"),
        "C": receipt("C", "1200", "003", text=ALTERED_TEXT), "D": receipt("D", "300", "004"),
    }
    records = [
        photo("A", "altered_total", "confirmed", "1200", "200", "001"),
        photo("B", "altered_total", "probable", "1180", "180", "002"),
    ]
    rows = build_ledger(claims, receipts, [], records)

    assert {r["finding_category"] for r in rows_for(rows, "A")} >= {CONFIRMED}
    assert {r["finding_category"] for r in rows_for(rows, "B")} >= {PROBABLE}
    c_rows = rows_for(rows, "C")
    assert any(r["finding_category"] == LEAD and r["finding_type"].startswith("total_not_supported") for r in c_rows)
    assert not any(r["finding_category"] in (CONFIRMED, PROBABLE) for r in c_rows)
    assert any(r["finding_category"] == POLICY and r["finding_type"] == "policy_fuel_field_day" for r in rows_for(rows, "D"))


def test_excess_over_bill_comes_from_the_photo_amount():
    rows = build_ledger(
        [claim("A", "1200")], {"A": receipt("A", "1200")}, [],
        [photo("A", "altered_total", "confirmed", "1200", "200")],
    )

    row = next(r for r in rows if r["finding_category"] == CONFIRMED)
    assert row["excess_over_bill"] == Decimal("1000.00")
    assert row["counted_in_totals"] is True
    assert row["counted_measure"] == "excess_over_bill"
    assert row["gross_claim_exposure"] is None


def test_ocr_lead_without_supported_amount_has_no_invented_exposure():
    rows = build_ledger([claim("C", "1200")], {"C": receipt("C", "1200", text=ALTERED_TEXT)}, [], [])

    lead = next(r for r in rows if r["finding_type"].startswith("total_not_supported"))
    assert lead["excess_over_bill"] is None
    assert lead["photo_supported_amount"] is None
    assert counted(rows) == []


def test_same_employee_group_keeps_earliest_copy_and_counts_each_extra_once():
    claims = [
        claim("X", "500", emp="E1", submitted="2026-06-01"),
        claim("Y", "500", emp="E1", submitted="2026-06-05"),
        claim("Z", "500", emp="E1", submitted="2026-06-09"),
    ]
    receipts = {cid: receipt(cid, "500", image_hash="same") for cid in "XYZ"}
    rows = build_ledger(claims, receipts, [], [])

    dup = [r for r in rows if r["finding_type"] == "duplicate_exact_image"]
    assert {r["duplicate_group_id"] for r in dup} == {"DG-001"}
    assert {r["retained_claim_id"] for r in dup} == {"X"}
    assert {r["payer_status"] for r in dup} == {
        "same employee: duplicate submission by one claimant; earliest submission kept"
    }

    kept = [r for r in dup if r["claim_id"] == "X"]
    assert kept and all(r["finding_category"] == RETAINED and r["gross_claim_exposure"] == 0 for r in kept)

    extra = counted(rows)
    assert sorted(r["claim_id"] for r in extra) == ["Y", "Z"]
    assert sum(r["gross_claim_exposure"] for r in extra) == Decimal("1000.00")


def test_payer_unknown_group_is_counted_once_without_naming_a_claim():
    claims = [
        claim("X", "212.40", emp="E1", submitted="2026-06-01"),
        claim("Y", "210", emp="E2", submitted="2026-06-05"),
    ]
    receipts = {cid: receipt(cid, "212.40", image_hash="same") for cid in "XY"}
    rows = build_ledger(claims, receipts, [], [])

    members = [r for r in rows if r["finding_type"] == "duplicate_exact_image"]
    assert all(r["retained_claim_id"] == "" for r in members)
    assert all(r["gross_claim_exposure"] is None for r in members)
    assert all(r["payer_status"] == PAYER_UNKNOWN for r in members)

    group = [r for r in rows if r["finding_type"] == "duplicate_group_payer_unknown"]
    assert len(group) == 1
    assert group[0]["claim_id"] == "" and group[0]["emp_id"] == ""
    assert group[0]["related_claim_ids"] == "X;Y"
    assert "X (E1)" in group[0]["evidence"] and "Y (E2)" in group[0]["evidence"]
    # The smaller copy's value: no claim is singled out as the extra one.
    assert group[0]["gross_claim_exposure"] == Decimal("210.00")
    assert counted(rows) == group


def test_photo_confirmed_vehicle_owner_keeps_the_copy():
    claims = [
        claim("OWN", "300", emp="E1", category="Fuel", submitted="2026-07-10"),
        claim("COL", "300", emp="E2", category="Fuel", submitted="2026-06-01"),
    ]
    receipts = {
        "OWN": {**receipt("OWN", "300", "040", number="R9"), "vehicle_no": "MH31FA2290"},
        "COL": {**receipt("COL", "300", "041", number="R9"), "vehicle_no": "MH31FA2290"},
    }
    employees = [{"emp_id": "E1", "vehicle_no": "MH31 FA 2290"}, {"emp_id": "E2", "vehicle_no": "MH31 EK 4471"}]
    rows = build_ledger(claims, receipts, employees, [photo("COL", "colleague_vehicle", "confirmed", "300", "", "041")])

    dup = [r for r in rows if r["duplicate_group_id"]]
    # COL was submitted first, but the plate on the bill belongs to E1.
    assert {r["retained_claim_id"] for r in dup} == {"OWN"}
    assert {r["payer_status"] for r in dup} == {PAYER_VEHICLE_OWNER}
    assert "who paid is not established" in PAYER_VEHICLE_OWNER
    assert [r["claim_id"] for r in counted(rows)] == ["COL"]


def scenario_a(supported_on_b="200"):
    """Audit Scenario A: one Rs 1,200 bill claimed by two employees."""
    claims = [
        claim("A", "1200", emp="E1", submitted="2026-07-01"),
        claim("B", "1200", emp="E2", submitted="2026-07-05"),
    ]
    receipts = {"A": receipt("A", "1200", "001", image_hash="same"),
                "B": receipt("B", "1200", "002", image_hash="same")}
    records = [photo("B", "altered_total", "confirmed", "1200", supported_on_b, "002")]
    return build_ledger(claims, receipts, [], records)


def test_payer_unknown_group_and_member_excess_are_not_both_counted():
    rows = scenario_a()

    # If A is the valid copy, B is wholly extra (1,200) and its excess is
    # already inside that; the least the group can be is 2,400 - 1,200.
    assert sum(r[r["counted_measure"]] for r in counted(rows)) == Decimal("1200.00")
    assert [r["finding_type"] for r in counted(rows)] == ["duplicate_group_payer_unknown"]

    member_excess = next(r for r in rows if r["claim_id"] == "B" and r["finding_type"] == "altered_total")
    assert member_excess["excess_over_bill"] == Decimal("1000.00")
    assert member_excess["status"] == "not counted separately: included in payer-unknown group DG-001"


def test_payer_unknown_group_uses_confirmed_bill_amount_when_it_is_the_largest_valid_copy():
    claims = [
        claim("A", "1200", emp="E1", submitted="2026-07-01"),
        claim("B", "300", emp="E2", submitted="2026-07-05"),
    ]
    receipts = {"A": receipt("A", "1200", "001", image_hash="h"), "B": receipt("B", "1200", "002", image_hash="h")}
    records = [photo("A", "overclaim", "confirmed", "1200", "250", "001")]
    rows = build_ledger(claims, receipts, [], records)

    # Valid copy is at most max(250, 300) = 300, so 1,500 - 300 = 1,200.
    group = next(r for r in rows if r["finding_type"] == "duplicate_group_payer_unknown")
    assert group["gross_claim_exposure"] == Decimal("1200.00")
    assert sum(r[r["counted_measure"]] for r in counted(rows)) == Decimal("1200.00")


def test_member_excess_still_counts_when_the_group_is_not_counted():
    claims = [
        claim("A", "1200", emp="E1", split="train", status="approved", submitted="2026-07-01"),
        claim("B", "1200", emp="E2", split="train", status="rejected", submitted="2026-07-05"),
    ]
    receipts = {"A": receipt("A", "1200", "001", image_hash="same"),
                "B": receipt("B", "1200", "002", image_hash="same")}
    rows = build_ledger(claims, receipts, [], [photo("A", "altered_total", "confirmed", "1200", "200", "001")])

    assert [(r["claim_id"], r["finding_type"]) for r in counted(rows)] == [("A", "altered_total")]
    assert counted(rows)[0]["excess_over_bill"] == Decimal("1000.00")


def test_kept_copy_wording_never_claims_the_payer_is_known():
    claims = [claim("K", "300", emp="E1", submitted="2026-06-01"), claim("L", "300", emp="E2", submitted="2026-06-10")]
    receipts = {"K": receipt("K", "300", "010", number="R1"), "L": receipt("L", "300", "011", number="R1")}
    records = [photo("L", "duplicate_same_bill", "confirmed", "300", "300", "011", related="K", retained="K")]
    rows = build_ledger(claims, receipts, [], records)

    dup = [r for r in rows if r["duplicate_group_id"]]
    assert {r["payer_status"] for r in dup} == {PAYER_OWNER_ON_PHOTO}
    text = " ".join(str(r["payer_status"]) + " " + str(r["conclusion"]) for r in rows).lower()
    assert "established in the photo review" not in text
    assert "who paid is not established" in text


def test_payer_unknown_group_with_one_rejected_copy_is_not_counted():
    claims = [
        claim("A", "448.40", emp="E1", split="train", status="approved", submitted="2026-06-01"),
        claim("B", "448.40", emp="E2", split="train", status="rejected", submitted="2026-07-01"),
    ]
    receipts = {cid: receipt(cid, "448.40", image_hash="h") for cid in "AB"}
    rows = build_ledger(claims, receipts, [], [])

    group = next(r for r in rows if r["finding_type"] == "duplicate_group_payer_unknown")
    assert group["exposure_basis"].startswith("not counted")
    assert "no extra copy is valued" in group["evidence"]
    assert counted(rows) == []


def test_claim_with_several_findings_is_counted_once():
    claims = [claim("K", "300", emp="E1", category="Fuel", submitted="2026-06-01"),
              claim("L", "300", emp="E2", category="Fuel", submitted="2026-06-10")]
    receipts = {"K": receipt("K", "300", "010", number="R1"), "L": receipt("L", "300", "011", number="R1")}
    records = [
        photo("L", "duplicate_same_bill", "confirmed", "300", "300", "011", related="K", retained="K"),
        photo("L", "colleague_vehicle", "confirmed", "300", "", "011"),
        photo("L", "hostile_text", "confirmed", "300", "", "011"),
    ]
    rows = build_ledger(claims, receipts, [], records)

    assert len(counted(rows_for(rows, "L"))) == 1
    assert counted(rows_for(rows, "L"))[0]["gross_claim_exposure"] == Decimal("300.00")
    assert counted(rows_for(rows, "K")) == []
    # The OCR same-bill lead is superseded by the photo finding.
    ocr = [r for r in rows_for(rows, "L") if r["finding_type"] == "duplicate_same_bill_ocr"]
    assert ocr and ocr[0]["status"] == "corroborated by photo finding"


def test_missing_evidence_is_a_policy_question_without_money():
    rows = build_ledger(
        [claim("M", "400"), claim("N", "250", emp="E2")],
        {"N": receipt("N", "")}, [], [],
    )

    for claim_id in ("M", "N"):
        missing = [r for r in rows_for(rows, claim_id) if r["finding_type"] == "missing_receipt_evidence"]
        assert missing and missing[0]["finding_category"] == POLICY
    assert counted(rows) == []


def test_photo_record_that_does_not_match_source_is_unresolved():
    records = [
        photo("A", "altered_total", "confirmed", "1500", "200"),   # wrong amount
        photo("A", "overclaim", "confirmed", "1200", "200", prefix="999"),  # wrong image
        photo("GHOST", "altered_total", "confirmed", "100", "10"),  # unknown claim
    ]
    rows = build_ledger([claim("A", "1200")], {"A": receipt("A", "1200")}, [], records)

    unresolved = [r for r in rows if r["finding_category"] == UNRESOLVED]
    assert len(unresolved) == 3
    assert all(r["status"].startswith("record mismatch") for r in unresolved)
    assert not any(r["finding_category"] in (CONFIRMED, PROBABLE) for r in rows)
    assert counted(rows) == []


def test_lead_cleared_by_photo_is_not_counted():
    rows = build_ledger(
        [claim("C", "1200")], {"C": receipt("C", "1200", text=ALTERED_TEXT)}, [],
        [photo("C", "cleared_lead", "cleared", "1200", "1200")],
    )

    lead = next(r for r in rows if r["finding_type"].startswith("total_not_supported"))
    assert lead["status"] == "cleared by photo review"


def test_rejected_historical_claim_carries_no_counted_exposure():
    rows = build_ledger(
        [claim("R", "1200", split="train", status="rejected")], {"R": receipt("R", "1200")}, [],
        [photo("R", "altered_total", "confirmed", "1200", "200")],
    )

    assert counted(rows) == []
    assert rows_for(rows, "R")[0]["exposure_basis"].startswith("not counted")


def test_ocr_amount_gap_settled_by_source_records_is_not_counted():
    corrected = claim("S1", "600", split="train", status="approved")
    corrected.update(clerk_bill_amount="500", clerk_note="amt corrected to 500 as per bill")
    clerk_agrees = claim("S2", "100", emp="E2", split="train", status="approved")
    clerk_agrees.update(clerk_bill_amount="100", clerk_note="")
    open_gap = claim("S3", "568", emp="E3", split="train", status="approved")
    open_gap.update(clerk_bill_amount="368", clerk_note="")
    rows = build_ledger(
        [corrected, clerk_agrees, open_gap],
        {"S1": receipt("S1", "500", "030"), "S2": receipt("S2", "20", "031"), "S3": receipt("S3", "368", "032")},
        [], [],
    )

    status = {r["claim_id"]: r["status"] for r in rows if r["finding_type"] == "claim_differs_from_ocr_total"}
    assert status["S1"].startswith("clerk note records a correction")
    assert status["S2"].startswith("clerk-entered bill amount agrees")
    assert status["S3"] == "open"
    assert [r["claim_id"] for r in counted(rows)] == ["S3"]


def test_possible_duplicate_is_a_lead_without_money():
    claims = [claim("P", "330.40", emp="E1", category="Courier"), claim("Q", "330.40", emp="E2", category="Courier")]
    receipts = {"P": receipt("P", "330.40", "020", number="A1"), "Q": receipt("Q", "330.40", "021", number="B2")}
    rows = build_ledger(claims, receipts, [], [])

    possible = [r for r in rows if r["finding_type"] == "duplicate_possible"]
    assert possible and all(r["finding_category"] == LEAD for r in possible)
    assert all(r["gross_claim_exposure"] is None for r in possible)
    assert counted(rows) == []


def test_overlapping_parking_is_a_lead_without_money():
    def ticket_text(vendor, entry, exit_):
        return "\n".join([vendor, "Ticket No: 1", "Veh No : MH31EK4471", "In", f": 01/08/26 {entry}",
                          "Out", f": 01/08/26 {exit_}", "Amount Rs", "30.00"])

    claims = [claim("K", "30", emp="E1", category="Parking"), claim("L", "20", emp="E1", category="Parking")]
    receipts = {
        "K": {**receipt("K", "30", "030", number="1", vendor="SITABULDI MULTILEVEL PARKING",
                        text=ticket_text("SITABULDI MULTILEVEL PARKING", "09:28", "13:37")),
              "vehicle_no": "MH31EK4471", "receipt_date": "2026-08-01"},
        "L": {**receipt("L", "20", "031", number="2", vendor="MEDICAL SQUARE PAY & PARK",
                        text=ticket_text("MEDICAL SQUARE PAY & PARK", "10:07", "14:42")),
              "vehicle_no": "MH31EK4471", "receipt_date": "2026-08-01"},
    }
    employees = [{"emp_id": "E1", "vehicle_no": "MH31EK4471"}]
    rows = build_ledger(claims, receipts, employees, [])

    conflict = [r for r in rows if r["finding_type"] == "parking_time_conflict"]
    assert sorted(r["claim_id"] for r in conflict) == ["K", "L"]
    assert all(r["finding_category"] == LEAD and not r["duplicate_group_id"] for r in conflict)
    assert all(r["gross_claim_exposure"] is None and r["excess_over_bill"] is None for r in conflict)
    assert "09:28-13:37" in conflict[0]["evidence"] and "not established" in conflict[0]["conclusion"]
    assert counted(rows) == []


def test_same_ticket_with_misread_car_park_keeps_duplicate_accounting():
    def ticket_text(vendor):
        return "\n".join([vendor, "Ticket No: 110914", "Veh No : MH31FG6627", "In", ": 19/06/26 11:10",
                          "Out", ": 19/06/26 14:13", "Amount Rs", "30.00"])

    claims = [
        claim("CLM-30566", "30", emp="E1", category="Parking", split="train", submitted="2026-06-20", status="approved"),
        claim("CLM-30799", "30", emp="E1", category="Parking", split="train", submitted="2026-07-02", status="approved"),
    ]
    receipts = {}
    for claim_id, prefix, vendor in (("CLM-30566", "175", "SITABULDI MULTILEVEL PARKING"),
                                     ("CLM-30799", "247", "SITABULDI MULTILEVEL PARKNG")):
        receipts[claim_id] = {**receipt(claim_id, "30.00", prefix, text=ticket_text(vendor), number="110914",
                                        vendor=vendor),
                              "vehicle_no": "MH31FG6627", "receipt_date": "2026-06-19"}
    rows = build_ledger(claims, receipts, [{"emp_id": "E1", "vehicle_no": "MH31FG6627"}], [])

    assert not any(r["finding_type"] == "parking_time_conflict" for r in rows)
    dup = [r for r in rows if r["finding_type"] == "duplicate_same_bill_ocr"]
    assert {r["duplicate_group_id"] for r in dup} == {"DG-001"} and len(dup) == 2
    assert [(r["claim_id"], r["gross_claim_exposure"]) for r in counted(rows)] == [("CLM-30799", Decimal("30.00"))]


def test_wording_states_evidence_not_misconduct_or_payment():
    rows = build_ledger(
        [claim("A", "1200", split="train", status="approved")], {"A": receipt("A", "1200")}, [],
        [photo("A", "altered_total", "confirmed", "1200", "200")],
    )

    text = " ".join(str(value) for row in rows for value in row.values()).lower()
    assert "fraud" not in text
    assert "recovered" not in text
    assert all(row["payment_status"] == "not recorded in source data" for row in rows)
    assert counted(rows)[0]["exposure_basis"] == "historically approved; amount paid not recorded"


def test_summary_totals_add_counted_rows_only():
    rows = build_ledger(
        [claim("A", "1200"), claim("B", "1180", emp="E2")],
        {"A": receipt("A", "1200", "001"), "B": receipt("B", "1180", "002")}, [],
        [photo("A", "altered_total", "confirmed", "1200", "200", "001"),
         photo("B", "altered_total", "probable", "1180", "180", "002")],
    )

    totals = {(s["finding_category"], s["measure"]): (s["items"], s["amount"]) for s in summarize(rows)}
    assert totals[(CONFIRMED, "excess_over_bill")] == (1, Decimal("1000.00"))
    assert totals[(PROBABLE, "excess_over_bill")] == (1, Decimal("1000.00"))


@pytest.mark.skipif(
    not Path("audit/photo_review_findings.csv").is_file()
    or not Path("reports/ocr_extractions_v3.csv").is_file(),
    reason="project data not available",
)
def test_project_ledger_matches_the_audited_findings():
    rows = build_ledger(*load_project_inputs())

    assert not [r for r in rows if r["finding_category"] == UNRESOLVED]
    by_claim = {r["claim_id"]: r for r in counted(rows) if r["claim_id"]}
    assert by_claim["CLM-31192"]["finding_category"] == CONFIRMED
    assert by_claim["CLM-31192"]["excess_over_bill"] == Decimal("1000.00")
    assert by_claim["CLM-31203"]["finding_category"] == PROBABLE
    assert "CLM-31478" not in by_claim
    assert by_claim["CLM-31497"]["gross_claim_exposure"] == Decimal("1170.00")
    assert "CLM-31310" not in by_claim
    assert len([r for r in counted(rows) if r["claim_id"] == "CLM-31120"]) == 1

    # Fixture additions from the ledger audit are now photo-confirmed.
    assert by_claim["CLM-30736"]["finding_category"] == CONFIRMED
    assert by_claim["CLM-30736"]["gross_claim_exposure"] == Decimal("2400.00")
    assert by_claim["CLM-30982"]["finding_category"] == CONFIRMED
    assert any(
        r["claim_id"] == "CLM-30982" and r["finding_type"] == "hostile_text"
        and r["finding_category"] == CONFIRMED for r in rows
    )

    # Kept copies are not presented as confirmed problem claims.
    for kept in ("CLM-30533", "CLM-30741", "CLM-30469", "CLM-30614", "CLM-30660", "CLM-30688"):
        dup = [r for r in rows if r["claim_id"] == kept and r["duplicate_group_id"]]
        assert dup and not any(r["finding_category"] == CONFIRMED for r in dup), kept

    # Payer wording: never "established"; a cross-employee kept copy names the
    # bill or vehicle owner, not the payer.
    assert not any("established in the photo review" in r["payer_status"] for r in rows)
    for kept_pair in ("CLM-31310", "CLM-30614", "CLM-30687"):
        dup = [r for r in rows if r["claim_id"] == kept_pair and r["duplicate_group_id"]]
        assert dup and all("who paid is not established" in r["payer_status"] for r in dup), kept_pair

    # Corrected fixture notes for the colleague-vehicle partners, without an upgrade.
    notes = {r["claim_id"]: r["evidence"] for r in rows if r["finding_type"] == "colleague_vehicle"}
    assert "image 028" in notes["CLM-30954"] and "not opened" not in notes["CLM-30954"]
    assert "image 214" in notes["CLM-31023"] and "not opened" not in notes["CLM-31023"]
    for partner in ("CLM-30660", "CLM-30688"):
        dup = [r for r in rows if r["claim_id"] == partner and r["duplicate_group_id"]]
        assert dup and all(r["finding_category"] == LEAD for r in dup), partner

    # Cross-employee duplicates with an unknown payer name no single claim.
    # Same vehicle in two car parks at overlapping times: an uncounted lead on both claims.
    for pair in (("CLM-30872", "CLM-31007"), ("CLM-31359", "CLM-31516")):
        for claim_id, other in (pair, pair[::-1]):
            conflict = [r for r in rows if r["claim_id"] == claim_id and r["finding_type"] == "parking_time_conflict"]
            assert len(conflict) == 1 and conflict[0]["related_claim_ids"] == other, claim_id
            assert not conflict[0]["counted_in_totals"]
    assert not any(r["finding_type"] == "parking_time_conflict"
                   for r in rows if r["claim_id"] in ("CLM-30566", "CLM-30799"))

    for pair in ("CLM-30608;CLM-31081", "CLM-30600;CLM-30963", "CLM-30661;CLM-30804", "CLM-31102;CLM-31275"):
        group = [r for r in counted(rows) if r["related_claim_ids"] == pair]
        assert len(group) == 1 and group[0]["claim_id"] == "", pair
        for claim_id in pair.split(";"):
            assert claim_id not in by_claim, claim_id
