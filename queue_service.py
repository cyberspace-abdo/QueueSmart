from datetime import datetime
from pathlib import Path

import qrcode

import database


def is_business_open(business):
    now = datetime.now().strftime("%H:%M")
    return business["opening_time"] <= now <= business["closing_time"]


def get_business_summary(business_id):
    tickets = database.get_tickets_for_business(business_id)
    waiting_tickets = [ticket for ticket in tickets if ticket["status"] == "waiting"]
    return {
        "waiting_count": len(waiting_tickets),
        "current_ticket": get_current_customer(business_id),
        "estimated_waiting": sum(ticket["estimated_waiting_minutes"] for ticket in waiting_tickets),
    }


def get_current_customer(business_id):
    for ticket in database.get_tickets_for_business(business_id):
        if ticket["status"] in {"called", "in_service"}:
            return ticket
    return None


def recalculate_queue(business_id):
    tickets = database.get_tickets_for_business(business_id)
    waiting_tickets = [ticket for ticket in tickets if ticket["status"] == "waiting"]
    waiting_tickets.sort(key=lambda item: item["created_at"])

    running_total = 0
    for index, ticket in enumerate(waiting_tickets, start=1):
        duration = get_service_duration(ticket["service_id"])
        database.set_ticket_position(ticket["id"], index, running_total)
        running_total += duration

    for ticket in tickets:
        if ticket["status"] != "waiting":
            database.set_ticket_position(ticket["id"], None, 0)


def get_service_duration(service_id):
    service = database.get_service(service_id)
    return service["duration"] if service else 0


def get_ticket_message(ticket):
    if ticket["status"] == "completed":
        return "Your ticket has been completed."
    if ticket["status"] == "cancelled":
        return "Your ticket was cancelled."
    if ticket["status"] == "absent":
        return "You were marked absent."
    if ticket["status"] == "in_service":
        return "You are being served now."
    if ticket["status"] == "called":
        return "Please go to the business now."
    if ticket["position"] == 1:
        return "You are next."
    if ticket["position"] and ticket["position"] <= 3:
        return f"Your turn is approaching. There are {ticket['position'] - 1} customers before you."
    if ticket["position"]:
        return f"There are {ticket['position'] - 1} customers before you."
    return "You are waiting for your turn."


def get_daily_stats(business_id):
    tickets = database.get_tickets_for_business(business_id)
    today = datetime.now().strftime("%Y-%m-%d")
    todays_tickets = [ticket for ticket in tickets if ticket["created_at"].startswith(today)]

    completed_count = sum(1 for ticket in todays_tickets if ticket["status"] == "completed")
    cancelled_count = sum(1 for ticket in todays_tickets if ticket["status"] == "cancelled")
    average_waiting = 0
    if todays_tickets:
        average_waiting = round(sum(ticket["estimated_waiting_minutes"] for ticket in todays_tickets) / len(todays_tickets), 1)

    return {
        "ticket_count": len(todays_tickets),
        "completed_count": completed_count,
        "cancelled_count": cancelled_count,
        "average_waiting": average_waiting,
    }


def generate_qr_code(business_id, business):
    qr_dir = Path(__file__).resolve().parent / "qr_codes"
    qr_dir.mkdir(exist_ok=True)
    image_path = qr_dir / f"{business_id}.png"
    url = f"http://127.0.0.1:5000/business/{business_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(image_path)
    return f"/qr_codes/{business_id}.png"