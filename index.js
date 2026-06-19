// JavaScript to simulate our database
        const mockDatabase = {
            coffee: { status: "No Line (0-5m)", color: "#2ecc71", time: "Just now" },
            grocery: { status: "Busy (15m+)", color: "#e74c3c", time: "5 mins ago" },
            library: { status: "Moderate (5-15m)", color: "#f1c40f", time: "12 mins ago" }
        };

        // Function called when a user clicks a button to report
        function submitReport(statusLevel) {
            const selectedLoc = document.getElementById("location-select").value;
            
            // Determine color based on report
            let color = "#ccc";
            if (statusLevel.includes("No Line")) color = "#2ecc71";
            if (statusLevel.includes("Moderate")) color = "#f1c40f";
            if (statusLevel.includes("Busy")) color = "#e74c3c";

            // Update our temporary database
            mockDatabase[selectedLoc] = {
                status: statusLevel,
                color: color,
                time: "Updated just now"
            };

            // Force dashboard to refresh and show user their contribution worked
            document.getElementById("dashboard-select").value = selectedLoc;
            updateDashboard();
            
            alert("Thank you for your crowd-sourced report!");
        }

        // Function to update what is shown on screen
        function updateDashboard() {
            const currentSelection = document.getElementById("dashboard-select").value;
            const data = mockDatabase[currentSelection];
            const selectElement = document.getElementById("dashboard-select");
            const displayName = selectElement.options[selectElement.selectedIndex].text;

            if (data) {
                document.getElementById("display-name").innerText = displayName;
                document.getElementById("display-status").innerText = data.status;
                document.getElementById("display-status").style.color = data.color;
                document.getElementById("display-time").innerText = `Last reported: ${data.time}`;
                document.getElementById("display-dot").style.backgroundColor = data.color;
                document.getElementById("status-card").style.borderLeftColor = data.color;
            }
        }

        // Run once on page load to set initial dashboard view
        updateDashboard();