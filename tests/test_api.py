from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def valid_request():
    return {
        "claim": {
            "claim_id": "CLM-TEST-001",
            "category": "parking",
            "vendor": "Test Parking",
            "amount_claimed": 500,
        },
        "receipt": {
            "vendor": "Test Parking",
            "receipt_date": "2026-07-18",
            "receipt_number": "PARK-001",
            "gstin": "",
            "total_amount": 500,
            "readable": True,
        },
        "employee": {
            "emp_id": "EMP-001",
            "grade": "M1",
            "vehicle_no": "MH01AB1234",
        },
        "receipt_available": True,
        "duplicate_info": {
            "duplicate_detected": False,
            "possible_matches": [],
        },
    }


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["health"] == "/health"
    assert response.json()["docs"] == "/docs"


def test_decide_endpoint_approves_valid_parking_claim():
    response = client.post("/decide", json=valid_request())

    assert response.status_code == 200
    assert response.json()["claim_id"] == "CLM-TEST-001"
    assert response.json()["decision"] == "approve"
    assert response.json()["total_amount"] == 500.0


def test_decide_endpoint_reviews_missing_receipt_date():
    payload = valid_request()
    payload["receipt"]["receipt_date"] = ""

    response = client.post("/decide", json=payload)

    assert response.status_code == 200
    assert response.json()["decision"] == "review"


def test_decide_endpoint_reviews_duplicate_claim():
    payload = valid_request()
    payload["duplicate_info"]["duplicate_detected"] = True

    response = client.post("/decide", json=payload)

    assert response.status_code == 200
    assert response.json()["decision"] == "review"


def test_decide_endpoint_rejects_invalid_request_shape():
    response = client.post("/decide", json={"claim": "not-a-dictionary"})

    assert response.status_code == 422
