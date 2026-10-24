
from app.decision_engine import make_decision
from app.duplicate_detection import detect_duplicates


def claim(claim_id, emp_id, amount=335):
    return {"claim_id": claim_id, "emp_id": emp_id, "amount_claimed": amount}


def bill(number="8199", amount="335", date="2026-06-15", image="", vendor="PUNJABI TADKA DHABA"):
    return {
        "vendor": vendor,
        "receipt_number": number,
        "total_amount": amount,
        "receipt_date": date,
        "image_sha256": image,
    }


def test_bill_8199_photographed_twice_is_same_bill():
    # CLM-30469 and CLM-30665: separate photos of one bill, same employee.
    results = detect_duplicates(
        [claim("CLM-30469", "TPD-0412"), claim("CLM-30665", "TPD-0412")],
        {"CLM-30469": bill(image="aaa"), "CLM-30665": bill(date="", image="bbb")},
    )

    for claim_id, other in (("CLM-30469", "CLM-30665"), ("CLM-30665", "CLM-30469")):
        assert results[claim_id]["duplicate_detected"] is True
        assert results[claim_id]["match_type"] == "same_bill"
        assert results[claim_id]["possible_matches"] == [other]
        assert results[claim_id]["cross_employee"] is False


def test_exact_image_duplicate_across_employees_is_labelled_not_judged():
    # CLM-30600 / CLM-30963: the same image file under two employees.
    results = detect_duplicates(
        [claim("CLM-30600", "TPD-0388", 672), claim("CLM-30963", "TPD-0423", 672)],
        {
            "CLM-30600": bill("6175", "672", image="same", vendor="HOTEL SAIBABA BHOJNALAYA"),
            "CLM-30963": bill("", "672", image="same", vendor="HOTEL SAIBABA BHOJNALAYA"),
        },
    )

    result = results["CLM-30963"]
    assert result["match_type"] == "exact_image"
    assert result["cross_employee"] is True
    assert "payer not established" in result["reason"]
    assert "fraud" not in result["reason"].lower()


def test_vendor_spacing_does_not_hide_a_duplicate():
    # CLM-30608 / CLM-31081: OCR dropped a space in the vendor name.
    results = detect_duplicates(
        [claim("CLM-30608", "TPD-0478", 210), claim("CLM-31081", "TPD-0471", 212.4)],
        {
            "CLM-30608": bill("PP38188814", "212.40", vendor="PROMPT PARCEL SERVICES"),
            "CLM-31081": bill("PP38188814", "212.40", vendor="PROMPT PARCELSERVICES"),
        },
    )

    assert results["CLM-31081"]["match_type"] == "same_bill"


def test_reused_number_with_conflicting_amount_and_date_is_only_possible():
    results = detect_duplicates(
        [claim("A", "E1"), claim("B", "E2")],
        {"A": bill("002123", "300", "2026-06-10"), "B": bill("002123", "450", "2026-07-20")},
    )

    assert results["A"]["duplicate_detected"] is False
    assert results["A"]["match_type"] == "possible"


def test_unrelated_claims_are_not_matched():
    results = detect_duplicates(
        [claim("A", "E1"), claim("B", "E1")],
        {"A": bill("1"), "B": bill("2", "500", "2026-07-01")},
    )

    assert results["A"]["possible_matches"] == []


def parking(claim_id, emp_id, date="", ticket="", image=""):
    return (
        {"claim_id": claim_id, "emp_id": emp_id, "category": "Parking", "amount_claimed": "30"},
        {
            "vendor": "SITABULDI MULTILEVEL PARKING",
            "receipt_number": ticket,
            "total_amount": "30.00",
            "receipt_date": date,
            "image_sha256": image,
        },
    )


def run(*entries):
    return detect_duplicates([c for c, _ in entries], {c["claim_id"]: r for c, r in entries})


def test_routine_parking_across_employees_is_not_matched():
    results = run(
        parking("P1", "TPD-0412", "2026-07-01", "110001"),
        parking("P2", "TPD-0497", "2026-07-01", "110002"),
        parking("P3", "TPD-0431", "", ""),
    )

    assert all(result["possible_matches"] == [] for result in results.values())


def test_parking_with_same_ticket_or_image_is_still_matched():
    by_ticket = run(parking("P1", "TPD-0412", ticket="110914"), parking("P2", "TPD-0497", ticket="110914"))
    assert by_ticket["P2"]["match_type"] == "same_bill"

    by_image = run(parking("P1", "TPD-0412", image="h"), parking("P2", "TPD-0497", image="h"))
    assert by_image["P2"]["match_type"] == "exact_image"


def test_weak_match_needs_both_bill_dates():
    one_date = detect_duplicates(
        [claim("A", "E1"), claim("B", "E2")],
        {"A": bill("1", date="2026-07-01"), "B": bill("2", date="")},
    )
    assert one_date["A"]["possible_matches"] == []

    same_date = detect_duplicates(
        [claim("A", "E1"), claim("B", "E2")],
        {"A": bill("1", date="2026-07-01"), "B": bill("2", date="2026-07-01")},
    )
    assert same_date["A"]["match_type"] == "possible"
    assert "receipt number not matched" in same_date["A"]["reason"]


def test_reasons_say_what_matched():
    results = detect_duplicates(
        [claim("CLM-30469", "TPD-0412"), claim("CLM-30665", "TPD-0412")],
        {"CLM-30469": bill(), "CLM-30665": bill(date="")},
    )

    assert "same vendor and receipt number, same amount" in results["CLM-30665"]["reason"]


def test_duplicate_reason_and_flags_reach_the_decision():
    info = detect_duplicates(
        [claim("CLM-30469", "TPD-0412"), claim("CLM-30665", "TPD-0412")],
        {"CLM-30469": bill(image="aaa"), "CLM-30665": bill(image="bbb")},
    )["CLM-30665"]

    result = make_decision(
        {"claim_id": "CLM-30665", "category": "Food", "amount_claimed": "335.00"},
        {**bill(), "readable": True},
        {"emp_id": "TPD-0412", "grade": "M1"},
        duplicate_info=info,
    )

    assert result["decision"] == "review"
    assert "duplicate_same_bill" in result["flags"]
    assert "CLM-30469" in result["reason"]


SITABULDI = "SITABULDI MULTILEVEL PARKING"
MEDICAL_SQUARE = "MEDICAL SQUARE PAY & PARK"
REGISTRY = {"MH31DX0981": "TPD-0431", "MH31EK4471": "TPD-0412", "MH31FG6627": "TPD-0497"}


def ticket(claim_id, emp_id, vendor, number, plate, day, entry, exit_, amount="30.00",
           category="Parking", date=""):
    """A parking claim whose OCR text follows the ticket layout in the photos."""
    lines = [vendor, "Nagpur Municipal Corporation", f"Ticket No: {number}", f"Veh No : {plate}",
             "Type", "2W (Day rate)", "In", f": {day} {entry}" if entry else ":",
             "Out", f": {day} {exit_}" if exit_ else ":", "Amount Rs", amount]
    return (
        {"claim_id": claim_id, "emp_id": emp_id, "category": category, "amount_claimed": amount},
        {"vendor": vendor, "receipt_number": number, "total_amount": amount,
         "receipt_date": date, "vehicle_no": plate, "raw_text": "\n".join(lines)},
    )


def run_tickets(*entries, registry=REGISTRY):
    return detect_duplicates(
        [c for c, _ in entries], {c["claim_id"]: r for c, r in entries}, registry
    )


def test_same_vehicle_in_two_car_parks_at_once_conflicts_training_pair():
    # CLM-30872 / CLM-31007: photo-verified, 2 July 2026.
    results = run_tickets(
        ticket("CLM-30872", "TPD-0431", SITABULDI, "114424", "MH31DX0981", "02/07/26", "11:39", "13:37"),
        ticket("CLM-31007", "TPD-0431", MEDICAL_SQUARE, "104727", "MH31DX0981", "02/07/26", "12:49", "16:22", "20.00"),
    )

    for claim_id, other in (("CLM-30872", "CLM-31007"), ("CLM-31007", "CLM-30872")):
        assert results[claim_id]["matched"] == {other: "parking_overlap"}
        assert results[claim_id]["duplicate_detected"] is False
    reason = results["CLM-31007"]["reason"]
    assert "11:39-13:37" in reason and "12:49-16:22" in reason and "2026-07-02" in reason
    assert "not established" in reason and "fraud" not in reason.casefold()


def test_overlapping_parking_sends_low_value_test_claims_to_review():
    # CLM-31516 / CLM-31359: photo-verified, 1 August 2026; Rs 30 and Rs 20.
    entries = (
        ticket("CLM-31516", "TPD-0412", SITABULDI, "119019", "MH31EK4471", "01/08/26", "09:28", "13:37"),
        ticket("CLM-31359", "TPD-0412", MEDICAL_SQUARE, "105547", "MH31EK4471", "01/08/26", "10:07", "14:42", "20.00"),
    )
    results = run_tickets(*entries)

    for claim, receipt in entries:
        decision = make_decision(
            claim, {**receipt, "readable": True}, {"emp_id": "TPD-0412", "grade": "M1"},
            duplicate_info=results[claim["claim_id"]], vehicle_registry=REGISTRY,
        )
        assert decision["decision"] == "review"
        assert "parking_time_conflict" in decision["flags"]
        assert not any(flag.startswith("duplicate_") for flag in decision["flags"])


def test_identical_parking_ticket_in_two_claims_is_a_duplicate_not_an_overlap():
    # CLM-30566 / CLM-30799: two photos of Sitabuldi ticket 110914, 19 June 2026.
    results = run_tickets(
        ticket("CLM-30566", "TPD-0497", SITABULDI, "110914", "MH31FG6627", "19/06/26", "11:10", "14:13"),
        ticket("CLM-30799", "TPD-0497", SITABULDI, "110914", "MH31FG6627", "19/06/26", "11:10", "14:13"),
    )

    assert results["CLM-30799"]["matched"] == {"CLM-30566": "same_bill"}
    assert results["CLM-30799"]["duplicate_detected"] is True


def test_same_vehicle_parking_twice_a_day_without_overlap_is_not_flagged():
    results = run_tickets(
        ticket("A", "TPD-0412", SITABULDI, "1", "MH31EK4471", "01/08/26", "09:00", "11:00"),
        ticket("B", "TPD-0412", MEDICAL_SQUARE, "2", "MH31EK4471", "01/08/26", "11:00", "13:00"),
    )
    assert all(result["matched"] == {} for result in results.values())


def test_different_vehicles_at_the_same_time_are_not_flagged():
    results = run_tickets(
        ticket("A", "TPD-0412", SITABULDI, "1", "MH31EK4471", "01/08/26", "09:00", "12:00"),
        ticket("B", "TPD-0431", MEDICAL_SQUARE, "2", "MH31DX0981", "01/08/26", "10:00", "13:00"),
    )
    assert all(result["matched"] == {} for result in results.values())


def test_missing_invalid_or_unregistered_ticket_details_are_not_matched():
    known = ticket("A", "TPD-0412", SITABULDI, "1", "MH31EK4471", "01/08/26", "09:00", "12:00")
    for uncertain in (
        ticket("B", "TPD-0412", MEDICAL_SQUARE, "2", "MH31EK4471", "01/08/26", "10:00", ""),       # no exit time
        ticket("B", "TPD-0412", MEDICAL_SQUARE, "2", "MH31EK4471", "38/07/26", "10:00", "11:00"),  # invalid date
        ticket("B", "TPD-0412", MEDICAL_SQUARE, "2", "", "01/08/26", "10:00", "11:00"),            # no plate
        ticket("B", "TPD-0412", MEDICAL_SQUARE, "2", "MH31EK4471", "01/08/26", "10:00", "11:00",
               date="2026-08-02"),                                                                 # dates disagree
    ):
        results = run_tickets(known, uncertain)
        assert all(result["matched"] == {} for result in results.values())

    unregistered = run_tickets(
        ticket("A", "TPD-0412", SITABULDI, "1", "MH49ZZ0001", "01/08/26", "09:00", "12:00"),
        ticket("B", "TPD-0412", MEDICAL_SQUARE, "2", "MH49ZZ0001", "01/08/26", "10:00", "11:00"),
    )
    assert all(result["matched"] == {} for result in unregistered.values())


def test_non_parking_claims_are_not_checked_for_parking_times():
    results = run_tickets(
        ticket("A", "TPD-0412", SITABULDI, "1", "MH31EK4471", "01/08/26", "09:00", "12:00"),
        ticket("B", "TPD-0412", MEDICAL_SQUARE, "2", "MH31EK4471", "01/08/26", "10:00", "11:00",
               category="Fuel"),
    )
    assert all(result["matched"] == {} for result in results.values())


def test_same_ticket_with_car_park_name_misread_is_a_duplicate_not_an_overlap():
    # CLM-30566 / CLM-30799, ticket 110914. The photos show the same name; the
    # misspelling on one copy simulates an OCR misread.
    results = run_tickets(
        ticket("CLM-30566", "TPD-0497", SITABULDI, "110914", "MH31FG6627", "19/06/26", "11:10", "14:13"),
        ticket("CLM-30799", "TPD-0497", "SITABULDI MULTILEVEL PARKNG", "110914", "MH31FG6627",
               "19/06/26", "11:10", "14:13"),
    )

    for claim_id, other in (("CLM-30566", "CLM-30799"), ("CLM-30799", "CLM-30566")):
        assert results[claim_id]["matched"] == {other: "same_bill"}
        assert results[claim_id]["duplicate_detected"] is True


def test_genuine_overlap_is_kept_beside_a_misread_duplicate():
    results = run_tickets(
        ticket("A", "TPD-0412", SITABULDI, "119019", "MH31EK4471", "01/08/26", "09:28", "13:37"),
        ticket("B", "TPD-0412", "SITABULDI MULTILEVEL PARKNG", "119019", "MH31EK4471", "01/08/26", "09:28", "13:37"),
        ticket("C", "TPD-0412", MEDICAL_SQUARE, "105547", "MH31EK4471", "01/08/26", "10:07", "14:42", "20.00"),
    )

    assert results["A"]["matched"] == {"B": "same_bill", "C": "parking_overlap"}
    assert results["C"]["matched"] == {"A": "parking_overlap", "B": "parking_overlap"}


def test_shared_ticket_number_at_different_car_parks_and_times_is_not_merged():
    results = run_tickets(
        ticket("A", "TPD-0412", SITABULDI, "105000", "MH31EK4471", "01/08/26", "09:00", "10:00"),
        ticket("B", "TPD-0412", MEDICAL_SQUARE, "105000", "MH31EK4471", "01/08/26", "15:00", "16:00", "20.00"),
    )
    assert all(result["matched"] == {} for result in results.values())


def test_shared_ticket_number_with_overlapping_different_times_is_an_overlap():
    results = run_tickets(
        ticket("A", "TPD-0412", SITABULDI, "105000", "MH31EK4471", "01/08/26", "09:00", "12:00"),
        ticket("B", "TPD-0412", MEDICAL_SQUARE, "105000", "MH31EK4471", "01/08/26", "10:00", "11:00", "20.00"),
    )
    assert results["A"]["matched"] == {"B": "parking_overlap"}
    assert results["B"]["duplicate_detected"] is False
