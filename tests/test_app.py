import importlib
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture()
def app_module(tmp_path, monkeypatch):
    db_path = tmp_path / "noubti-test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://127.0.0.1:5000")

    for name in ["app", "database", "queue_service"]:
        sys.modules.pop(name, None)

    module = importlib.import_module("app")
    module.app.config.update(TESTING=True)
    return module


@pytest.fixture()
def client(app_module):
    return app_module.app.test_client()


def sample_business_and_service(app_module):
    business = app_module.database.get_all_businesses()[0]
    service = app_module.database.get_services_for_business(business["id"])[0]
    return business, service


def create_ticket(app_module, customer_name="Test Customer", service=None):
    business, default_service = sample_business_and_service(app_module)
    service = service or default_service
    ticket = app_module.database.create_ticket(business["id"], service["id"], customer_name, "0612345678")
    app_module.queue_service.recalculate_queue(business["id"])
    return app_module.database.get_ticket(ticket["id"])


def test_application_starts_and_health_route(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"database": "connected", "status": "ok"}


def test_home_and_business_page_load(client, app_module):
    business, _ = sample_business_and_service(app_module)
    assert client.get("/").status_code == 200
    response = client.get(f"/business/{business['id']}")
    assert response.status_code == 200
    assert b"Noubti Barber" in response.data


def test_database_initialization_does_not_duplicate_seed_data(app_module):
    app_module.database.init_db()
    app_module.database.init_db()
    business = app_module.database.get_all_businesses()[0]
    services = app_module.database.get_services_for_business(business["id"])
    assert len(app_module.database.get_all_businesses()) == 1
    assert [service["name"] for service in services].count("Haircut") == 1
    assert len(services) == 3


def test_ticket_creation_and_unique_numbering(app_module):
    first = create_ticket(app_module, "First")
    second = create_ticket(app_module, "Second")
    assert first["ticket_number"] == "A001"
    assert second["ticket_number"] == "A002"


def test_queue_position_and_waiting_time(app_module):
    business, _ = sample_business_and_service(app_module)
    services = app_module.database.get_services_for_business(business["id"])
    first = create_ticket(app_module, "First", services[0])
    second = create_ticket(app_module, "Second", services[1])
    first = app_module.database.get_ticket(first["id"])
    second = app_module.database.get_ticket(second["id"])
    assert first["position"] == 1
    assert first["estimated_waiting_minutes"] == 0
    assert second["position"] == 2
    assert second["estimated_waiting_minutes"] == services[0]["duration"]
    assert business["name"] == "Noubti Barber"


def test_ticket_cancellation(client, app_module):
    ticket = create_ticket(app_module)
    response = client.post(f"/ticket/{ticket['id']}/cancel", follow_redirects=True)
    assert response.status_code == 200
    assert app_module.database.get_ticket(ticket["id"])["status"] == "cancelled"


def test_call_next_and_complete_ticket(client, app_module):
    business, _ = sample_business_and_service(app_module)
    ticket = create_ticket(app_module)
    response = client.post(f"/dashboard/{business['id']}/next", follow_redirects=True)
    assert response.status_code == 200
    assert app_module.database.get_ticket(ticket["id"])["status"] == "called"

    response = client.post(
        f"/dashboard/ticket/{ticket['id']}/status",
        data={"status": "completed"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    completed = app_module.database.get_ticket(ticket["id"])
    assert completed["status"] == "completed"
    assert completed["position"] is None


def test_service_creation(client, app_module):
    business, _ = sample_business_and_service(app_module)
    response = client.post(
        f"/dashboard/{business['id']}/services/add",
        data={"name": "Wash", "duration": "15", "price": "30"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    services = app_module.database.get_services_for_business(business["id"])
    assert any(service["name"] == "Wash" for service in services)


def test_missing_business_returns_404(client):
    assert client.get("/business/9999").status_code == 404


def test_ticket_api_returns_json(client, app_module):
    ticket = create_ticket(app_module)
    response = client.get(f"/api/ticket/{ticket['id']}")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ticket_number"] == "A001"
    assert payload["status"] == "waiting"
    assert payload["people_before"] == 0
