from flask import Flask, jsonify, redirect, render_template, request, url_for

import database
import queue_service

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key"


def init_app():
    database.init_db()
    for business in database.get_all_businesses():
        queue_service.recalculate_queue(business["id"])


init_app()


@app.route("/")
def home():
    businesses = database.get_all_businesses()
    return render_template("home.html", businesses=businesses)


@app.route("/business/<int:business_id>")
def business_page(business_id):
    business = database.get_business(business_id)
    if not business:
        return render_template("error.html", message="Business not found."), 404

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
    business = database.get_business(business_id)
    if not business:
        return render_template("error.html", message="Business not found."), 404

    if request.method == "POST":
        service_id = request.form.get("service_id", type=int)
        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()

        if not service_id or not customer_name or not phone:
            services = database.get_services_for_business(business_id)
            summary = queue_service.get_business_summary(business_id)
            return render_template(
                "business.html",
                business=business,
                services=services,
                summary=summary,
                is_open=queue_service.is_business_open(business),
                error="Please fill in every field.",
            ), 400

        service = database.get_service(service_id)
        if not service or service["business_id"] != business_id:
            return render_template("error.html", message="Service not found."), 404

        ticket = database.create_ticket(
            business_id=business_id,
            service_id=service_id,
            customer_name=customer_name,
            phone=phone,
        )
        queue_service.recalculate_queue(business_id)
        return render_template("take_ticket.html", business=business, ticket=ticket, service=service)

    return redirect(url_for("business_page", business_id=business_id))


@app.route("/ticket/<int:ticket_id>")
def ticket_status(ticket_id):
    ticket = database.get_ticket(ticket_id)
    if not ticket:
        return render_template("error.html", message="Ticket not found."), 404

    business = database.get_business(ticket["business_id"])
    service = database.get_service(ticket["service_id"])
    message = queue_service.get_ticket_message(ticket)
    return render_template("ticket_status.html", ticket=ticket, business=business, service=service, message=message)


@app.route("/ticket/<int:ticket_id>/cancel", methods=["POST"])
def cancel_ticket(ticket_id):
    ticket = database.get_ticket(ticket_id)
    if not ticket:
        return render_template("error.html", message="Ticket not found."), 404

    if ticket["status"] != "waiting":
        return render_template("error.html", message="Only waiting tickets can be cancelled."), 400

    database.update_ticket_status(ticket_id, "cancelled")
    queue_service.recalculate_queue(ticket["business_id"])
    return redirect(url_for("ticket_status", ticket_id=ticket_id))


@app.route("/dashboard/<int:business_id>")
def dashboard(business_id):
    business = database.get_business(business_id)
    if not business:
        return render_template("error.html", message="Business not found."), 404

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
    business = database.get_business(business_id)
    if not business:
        return render_template("error.html", message="Business not found."), 404

    next_ticket = database.get_next_waiting_ticket(business_id)
    if not next_ticket:
        return redirect(url_for("dashboard", business_id=business_id))

    database.update_ticket_status(next_ticket["id"], "called")
    queue_service.recalculate_queue(business_id)
    return redirect(url_for("dashboard", business_id=business_id))


@app.route("/dashboard/ticket/<int:ticket_id>/status", methods=["POST"])
def update_ticket_status(ticket_id):
    ticket = database.get_ticket(ticket_id)
    if not ticket:
        return render_template("error.html", message="Ticket not found."), 404

    new_status = request.form.get("status")
    if new_status not in {"waiting", "called", "in_service", "completed", "cancelled", "absent"}:
        return render_template("error.html", message="Invalid ticket status."), 400

    database.update_ticket_status(ticket_id, new_status)
    queue_service.recalculate_queue(ticket["business_id"])
    return redirect(url_for("dashboard", business_id=ticket["business_id"]))


@app.route("/dashboard/<int:business_id>/services")
def services_list(business_id):
    business = database.get_business(business_id)
    if not business:
        return render_template("error.html", message="Business not found."), 404

    services = database.get_services_for_business(business_id)
    return render_template("services.html", business=business, services=services)


@app.route("/dashboard/<int:business_id>/services/add", methods=["GET", "POST"])
def add_service(business_id):
    business = database.get_business(business_id)
    if not business:
        return render_template("error.html", message="Business not found."), 404

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        duration = request.form.get("duration", type=int)
        price = request.form.get("price", type=int)

        if not name or duration is None or price is None:
            return render_template("add_service.html", business=business, error="Please fill in every field."), 400

        database.create_service(business_id, name, duration, price)
        return redirect(url_for("services_list", business_id=business_id))

    return render_template("add_service.html", business=business)


@app.route("/dashboard/services/<int:service_id>/edit", methods=["GET", "POST"])
def edit_service(service_id):
    service = database.get_service(service_id)
    if not service:
        return render_template("error.html", message="Service not found."), 404

    business = database.get_business(service["business_id"])
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        duration = request.form.get("duration", type=int)
        price = request.form.get("price", type=int)

        if not name or duration is None or price is None:
            return render_template("edit_service.html", business=business, service=service, error="Please fill in every field."), 400

        database.update_service(service_id, name, duration, price)
        return redirect(url_for("services_list", business_id=service["business_id"]))

    return render_template("edit_service.html", business=business, service=service)


@app.route("/dashboard/services/<int:service_id>/delete", methods=["POST"])
def delete_service(service_id):
    service = database.get_service(service_id)
    if not service:
        return render_template("error.html", message="Service not found."), 404

    database.delete_service(service_id)
    return redirect(url_for("services_list", business_id=service["business_id"]))


@app.route("/business/<int:business_id>/qr")
def qr_code_page(business_id):
    business = database.get_business(business_id)
    if not business:
        return render_template("error.html", message="Business not found."), 404

    image_path = queue_service.generate_qr_code(business_id, business)
    return render_template("qr_code.html", business=business, image_path=image_path)


@app.route("/api/ticket/<int:ticket_id>")
def ticket_api(ticket_id):
    ticket = database.get_ticket(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    return jsonify({
        "ticket": dict(ticket),
        "message": queue_service.get_ticket_message(ticket)
    })


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", message="Page not found."), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)