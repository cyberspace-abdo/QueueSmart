document.addEventListener("DOMContentLoaded", function () {
    const ticketId = document.body.dataset.ticketId;
    if (!ticketId) return;

    const refreshStatus = () => {
        fetch(`/api/ticket/${ticketId}`)
            .then((response) => response.json())
            .then((data) => {
                const badge = document.getElementById("status-badge");
                const message = document.getElementById("status-message");
                if (badge) {
                    badge.textContent = data.ticket.status;
                    badge.className = `badge ${data.ticket.status}`;
                }
                if (message) {
                    message.textContent = data.message;
                }
            });
    };

    refreshStatus();
    window.setInterval(refreshStatus, 5000);
});