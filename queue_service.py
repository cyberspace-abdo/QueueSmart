import os
from datetime import datetime
from pathlib import Path

import qrcode

import database

ACTIVE_STATUSES = {"waiting", "called", "in_service"}
FINAL_STATUSES = {"completed", "cancelled", "absent"}


def is_business_open(business):
    opening = business.get("opening_time")
    closing = business.get("closing_time")
    if not opening or not closing:
        return False
    now = datetime.now().strftime("%H:%M")
    return opening <= now <= closing


def get_business_summary(business_id):
    tickets = database.get_tickets_for_business(business_id)
    active_tickets = [ticket for ticket in tickets if ticket["status"] in ACTIVE_STATUSES]
    waiting_tickets = [ticket for ticket in tickets if ticket["status"] == "waiting"]
    return {
        "waiting_count": len(waiting_tickets),
        "current_ticket": get_current_customer(business_id),
        "estimated_waiting": sum(ticket["service_duration"] or 0 for ticket in active_tickets),
    }


def get_current_customer(business_id):
    tickets = database.get_tickets_for_business(business_id)
    for status in ("in_service", "called"):
        for ticket in tickets:
            if ticket["status"] == status:
                return ticket
    return None


def recalculate_queue(business_id):
    tickets = database.get_tickets_for_business(business_id)
    active_tickets = [ticket for ticket in tickets if ticket["status"] in ACTIVE_STATUSES]
    active_tickets.sort(key=lambda item: (item["created_at"], item["id"]))

    running_total = 0
    for index, ticket in enumerate(active_tickets, start=1):
        database.set_ticket_position(ticket["id"], index, running_total)
        running_total += ticket["service_duration"] or 0

    for ticket in tickets:
        if ticket["status"] in FINAL_STATUSES:
            database.set_ticket_position(ticket["id"], None, 0)


def get_ticket_message(ticket):
    status = ticket["status"]
    if status == "completed":
        return "Your ticket is completed."
    if status == "cancelled":
        return "Your ticket was cancelled."
    if status == "absent":
        return "You were marked absent."
    if status == "in_service":
        return "Your service is in progress."
    if status == "called":
        return "Please go to the business now."

    people_before = get_people_before(ticket)
    if people_before == 0:
        return "You are next."
    if people_before <= 3:
        return "Your turn is approaching."
    return f"There are {people_before} customers before you."


def get_people_before(ticket):
    position = ticket.get("position")
    if not position:
        return 0
    return max(position - 1, 0)


def get_daily_stats(business_id):
    tickets = database.get_tickets_for_business(business_id)
    today = datetime.now().strftime("%Y-%m-%d")
    todays_tickets = [ticket for ticket in tickets if ticket["created_at"].startswith(today)]
    waiting_tickets = [ticket for ticket in todays_tickets if ticket["status"] == "waiting"]
    completed_count = sum(1 for ticket in todays_tickets if ticket["status"] == "completed")
    cancelled_count = sum(1 for ticket in todays_tickets if ticket["status"] == "cancelled")
    absent_count = sum(1 for ticket in todays_tickets if ticket["status"] == "absent")
    active_tickets = [ticket for ticket in todays_tickets if ticket["status"] in ACTIVE_STATUSES]
    average_waiting = 0
    if active_tickets:
        average_waiting = round(sum(ticket["estimated_waiting_minutes"] for ticket in active_tickets) / len(active_tickets), 1)

    return {
        "ticket_count": len(todays_tickets),
        "waiting_count": len(waiting_tickets),
        "completed_count": completed_count,
        "cancelled_count": cancelled_count,
        "absent_count": absent_count,
        "average_waiting": average_waiting,
    }


def get_ticket_payload(ticket_id):
    ticket = database.get_ticket(ticket_id)
    if not ticket:
        return None

    business_id = ticket["business_id"]
    current = get_current_customer(business_id)
    return {
        "id": ticket["id"],
        "ticket_number": ticket["ticket_number"],
        "status": ticket["status"],
        "position": ticket["position"],
        "people_before": get_people_before(ticket),
        "estimated_waiting_minutes": ticket["estimated_waiting_minutes"],
        "current_ticket": current["ticket_number"] if current else None,
        "notification_message": get_ticket_message(ticket),
    }


def generate_qr_code(business_id, business):
    qr_dir = Path(__file__).resolve().parent / "qr_codes"
    qr_dir.mkdir(exist_ok=True)
    image_path = qr_dir / f"business-{business_id}.png"
    if not image_path.exists():
        public_base_url = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
        url = f"{public_base_url}/business/{business_id}"
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(image_path)
    return f"/qr_codes/business-{business_id}.png"
