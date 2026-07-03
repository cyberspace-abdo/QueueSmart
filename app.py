import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory, url_for

import database
import queue_service

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["POLL_INTERVAL_SECONDS"] = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))

logging.basicConfig(level=logging.INFO)


def init_app():
    database.init_db()
    for business in database.get_all_businesses():
        queue_service.recalculate_queue(business["id"])


init_app()


def render_error(message, status_code=400):
    return render_template("error.html", message=message, status_code=status_code), status_code


def valid_phone(phone):
    if not phone:
        return True
    return re.fullmatch(r"(\+212|0)[5-7][0-9]{8}", phone.replace(" ", "")) is not None


def get_business_or_404(business_id):
    business = database.get_business(business_id)
    if not business:
        return None
    return business


@app.route("/health")
def health():
    try:
        with database.get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return jsonify({"status": "ok", "database": "connected"})
    except Exception as exc:
        app.logger.exception("Health check failed")
        return jsonify({"status": "error", "database": "unavailable", "error": str(exc)}), 500


@app.route("/")
def home():
    businesses = database.get_all_businesses()
    return render_template("home.html", businesses=businesses)


@app.route("/business/<int:business_id>")
def business_page(business_id):
    business = get_business_or_404(business_id)
    if not business:
        return render_error("Business not found.", 404)

    services = database.get_services_for_business(business_id)
    summary = queue_service.get_business_summary(business_id)
    return render_template(
        "business.html",
        business=business,
        services=services,
        summary=summary,
        is_open=queue_service.is_business_open(business),
    )


@app.route("/business/<int:business_id>/take-ticket", methods=["GET", "POST"])
def take_ticket(business_id):
    business = get_business_or_404(business_id)
    if not business:
        return render_error("Business not found.", 404)

    services = database.get_services_for_business(business_id)
    if request.method == "GET":
        return render_template("take_ticket.html", business=business, services=services)

    service_id = request.form.get("service_id", type=int)
    customer_name = request.form.get("customer_name", "").strip()
    phone = request.form.get("phone", "").strip()
    error = None

    if not customer_name:
        error = "Name is required."
    elif not service_id:
        error = "Please select a service."
    elif phone and not valid_phone(phone):
        error = "Use a valid Moroccan phone number such as 0612345678 or +212612345678."

    service = database.get_service(service_id) if service_id else None
    if not error and (not service or service["business_id"] != business_id):
        error = "Selected service is not available for this business."

    if error:
        summary = queue_service.get_business_summary(business_id)
        return render_template(
            "business.html",
            business=business,
            services=services,
            summary=summary,
            is_open=queue_service.is_business_open(business),
            error=error,
            form_data=request.form,
        ), 400

    ticket = database.create_ticket(
        business_id=business_id,
        service_id=service_id,
        customer_name=customer_name,
        phone=phone,
    )
    if not ticket:
        return render_error("Unable to create ticket.", 400)

    queue_service.recalculate_queue(business_id)
    ticket = database.get_ticket(ticket["id"])
    return render_template("ticket_created.html", business=business, ticket=ticket, service=service)


@app.route("/ticket/<int:ticket_id>")
def ticket_status(ticket_id):
    ticket = database.get_ticket(ticket_id)
    if not ticket:
        return render_error("Ticket not found.", 404)

    business = database.get_business(ticket["business_id"])
    service = database.get_service(ticket["service_id"])
    message = queue_service.get_ticket_message(ticket)
    return render_template(
        "ticket_status.html",
        ticket=ticket,
        business=business,
        service=service,
        message=message,
        poll_interval=app.config["POLL_INTERVAL_SECONDS"],
    )


@app.route("/ticket/<int:ticket_id>/cancel", methods=["POST"])
def cancel_ticket(ticket_id):
    ticket = database.get_ticket(ticket_id)
    if not ticket:
        return render_error("Ticket not found.", 404)

    if ticket["status"] != "waiting":
        return render_error("Only waiting tickets can be cancelled.", 400)

    database.update_ticket_status(ticket_id, "cancelled")
    queue_service.recalculate_queue(ticket["business_id"])
    return redirect(url_for("ticket_status", ticket_id=ticket_id))


@app.route("/dashboard/<int:business_id>")
def dashboard(business_id):
    business = get_business_or_404(business_id)
    if not business:
        return render_error("Business not found.", 404)

    services = database.get_services_for_business(business_id)
    tickets = database.get_tickets_for_business(business_id)
    stats = queue_service.get_daily_stats(business_id)
    current_customer = queue_service.get_current_customer(business_id)

    return render_template(
        "dashboard.html",
        business=business,
        services=services,
        tickets=tickets,
        current_customer=current_customer,
        stats=stats,
    )


@app.route("/dashboard/<int:business_id>/next", methods=["POST"])
def call_next_customer(business_id):
    business = get_business_or_404(business_id)
    if not business:
        return render_error("Business not found.", 404)

    current_customer = queue_service.get_current_customer(business_id)
    if current_customer:
        flash("Finish the current customer before calling the next one.", "warning")
        return redirect(url_for("dashboard", business_id=business_id))

    next_ticket = database.get_next_waiting_ticket(business_id)
    if next_ticket:
        database.update_ticket_status(next_ticket["id"], "called")
        queue_service.recalculate_queue(business_id)
    return redirect(url_for("dashboard", business_id=business_id))


@app.route("/dashboard/ticket/<int:ticket_id>/status", methods=["POST"])
def update_ticket_status(ticket_id):
    ticket = database.get_ticket(ticket_id)
    if not ticket:
        return render_error("Ticket not found.", 404)

    new_status = request.form.get("status")
    if new_status not in database.ALL_STATUSES:
        return render_error("Invalid ticket status.", 400)

    database.update_ticket_status(ticket_id, new_status)
    queue_service.recalculate_queue(ticket["business_id"])
    return redirect(url_for("dashboard", business_id=ticket["business_id"]))


@app.route("/dashboard/<int:business_id>/services")
def services_list(business_id):
    business = get_business_or_404(business_id)
    if not business:
        return render_error("Business not found.", 404)

    services = database.get_services_for_business(business_id)
    return render_template("services.html", business=business, services=services)


@app.route("/dashboard/<int:business_id>/services/add", methods=["GET", "POST"])
def add_service(business_id):
    business = get_business_or_404(business_id)
    if not business:
        return render_error("Business not found.", 404)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        duration = request.form.get("duration", type=int)
        price = request.form.get("price", type=int)
        error = validate_service_form(name, duration, price)
        if error:
            return render_template("add_service.html", business=business, error=error, form_data=request.form), 400

        database.create_service(business_id, name, duration, price)
        return redirect(url_for("services_list", business_id=business_id))

    return render_template("add_service.html", business=business)


@app.route("/dashboard/services/<int:service_id>/edit", methods=["GET", "POST"])
def edit_service(service_id):
    service = database.get_service(service_id)
    if not service:
        return render_error("Service not found.", 404)

    business = database.get_business(service["business_id"])
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        duration = request.form.get("duration", type=int)
        price = request.form.get("price", type=int)
        error = validate_service_form(name, duration, price)
        if error:
            return render_template("edit_service.html", business=business, service=service, error=error, form_data=request.form), 400

        database.update_service(service_id, name, duration, price)
        return redirect(url_for("services_list", business_id=service["business_id"]))

    return render_template("edit_service.html", business=business, service=service)


def validate_service_form(name, duration, price):
    if not name:
        return "Service name is required."
    if duration is None or duration <= 0:
        return "Duration must be a positive number of minutes."
    if price is None or price < 0:
        return "Price must be zero or more."
    return None


@app.route("/dashboard/services/<int:service_id>/delete", methods=["POST"])
def delete_service(service_id):
    service = database.get_service(service_id)
    if not service:
        return render_error("Service not found.", 404)

    if database.has_active_tickets_for_service(service_id):
        flash("This service has active tickets and cannot be deleted yet.", "warning")
    else:
        database.delete_service(service_id)
    return redirect(url_for("services_list", business_id=service["business_id"]))


@app.route("/business/<int:business_id>/qr")
def qr_code_page(business_id):
    business = get_business_or_404(business_id)
    if not business:
        return render_error("Business not found.", 404)

    image_path = queue_service.generate_qr_code(business_id, business)
    return render_template("qr_code.html", business=business, image_path=image_path, public_base_url=os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:5000"))


@app.route("/qr_codes/<path:filename>")
def qr_code_file(filename):
    return send_from_directory(BASE_DIR / "qr_codes", filename)


@app.route("/api/ticket/<int:ticket_id>")
def ticket_api(ticket_id):
    ticket = database.get_ticket(ticket_id)
    if ticket:
        queue_service.recalculate_queue(ticket["business_id"])
    payload = queue_service.get_ticket_payload(ticket_id)
    if not payload:
        return jsonify({"error": "Ticket not found"}), 404
    return jsonify(payload)


@app.errorhandler(400)
def bad_request(error):
    return render_error("Bad request.", 400)


@app.errorhandler(404)
def not_found(error):
    return render_error("Page not found.", 404)


@app.errorhandler(405)
def method_not_allowed(error):
    return render_error("That action does not support this HTTP method.", 405)


@app.errorhandler(500)
def server_error(error):
    app.logger.exception("Unhandled server error")
    return render_error("A server error occurred. Please try again.", 500)


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_ENV", "development") == "development", host="0.0.0.0", port=5000)
