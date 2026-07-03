document.addEventListener("DOMContentLoaded", function () {
    const config = window.NoubtiTicket || {};
    const ticketId = config.ticketId;
    if (!ticketId) return;

    const finalStatuses = new Set(["completed", "cancelled", "absent"]);
    let intervalId = null;

    const setText = (id, value) => {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    };

    const refreshStatus = () => {
        fetch(`/api/ticket/${ticketId}`)
            .then((response) => {
                if (!response.ok) throw new Error("Ticket status could not be loaded.");
                return response.json();
            })
            .then((data) => {
                const badge = document.getElementById("status-badge");
                if (badge) {
                    badge.textContent = data.status;
                    badge.className = `badge ${data.status}`;
                }

                setText("ticket-number", data.ticket_number);
                setText("status-message", data.notification_message);
                setText("position", data.position || "-");
                setText("people-before", data.people_before);
                setText("estimated-waiting", data.estimated_waiting_minutes);
                setText("current-ticket", data.current_ticket || "No ticket");

                if (finalStatuses.has(data.status) && intervalId) {
                    window.clearInterval(intervalId);
                }
            })
            .catch(() => {
                setText("status-message", "Ticket status is temporarily unavailable.");
            });
    };

    refreshStatus();
    intervalId = window.setInterval(refreshStatus, config.pollIntervalMs || 5000);
});
