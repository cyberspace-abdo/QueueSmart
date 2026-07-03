# Noubti Smart Queue

Noubti is a beginner-friendly Flask and SQLite queue management app for barbershops, cafes, restaurants, clinics, car washes, and other service businesses.

## Main Features
- Public business queue page with open/closed status
- Digital ticket creation with automatic numbers such as `A001`
- Ticket status page with polling updates
- Customer ticket cancellation while waiting
- Business dashboard for calling and updating customers
- Service add, edit, and delete screens
- Daily queue statistics from real database data
- QR code generation for the public business page
- Health check route at `/health`

## Technology Stack
- Python
- Flask
- SQLite
- Jinja templates
- Plain CSS
- Vanilla JavaScript
- qrcode
- Pillow
- python-dotenv
- pytest

## Folder Structure
```text
QueueSmart/
  app.py
  database.py
  queue_service.py
  requirements.txt
  README.md
  .env.example
  .gitignore
  instance/
    noubti.db
  qr_codes/
    .gitkeep
  static/
    css/style.css
    js/dashboard.js
    js/ticket.js
  templates/
    base.html
    home.html
    business.html
    take_ticket.html
    ticket_created.html
    ticket_status.html
    dashboard.html
    services.html
    add_service.html
    edit_service.html
    qr_code.html
    error.html
  tests/
    test_app.py
```

## Installation
Create and activate a virtual environment.

```bash
python -m venv venv
```

Windows:
```bash
venv\Scripts\activate
```

Linux/macOS:
```bash
source venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

## Environment Setup
Copy `.env.example` to `.env` and adjust values if needed.

```env
FLASK_ENV=development
SECRET_KEY=replace-with-a-random-secret
DATABASE_PATH=instance/noubti.db
PUBLIC_BASE_URL=http://127.0.0.1:5000
POLL_INTERVAL_SECONDS=5
```

`PUBLIC_BASE_URL` is used inside generated QR codes. For phone testing on the same network, set it to your computer IP, for example `http://192.168.1.10:5000`.

## Database Initialization
The database initializes automatically when the app starts. It creates the required tables and seeds one sample business:

- Noubti Barber
- Barbershop
- Rabat
- 09:00 to 20:00

Default services are inserted once:

- Haircut, 20 min, 50 DH
- Beard, 10 min, 25 DH
- Haircut and Beard, 30 min, 70 DH

Repeated runs do not duplicate this sample data.

## Run the Application
```bash
python app.py
```

Default local URLs:

- Home: `http://127.0.0.1:5000/`
- Health: `http://127.0.0.1:5000/health`
- Sample business: `http://127.0.0.1:5000/business/1`
- Dashboard: `http://127.0.0.1:5000/dashboard/1`
- Services: `http://127.0.0.1:5000/dashboard/1/services`
- QR code: `http://127.0.0.1:5000/business/1/qr`

## Customer Demo Flow
1. Open `/`.
2. Open the Noubti Barber queue.
3. Select a service.
4. Enter a name and optional Moroccan phone number.
5. Take a ticket.
6. Open the ticket status page.
7. Watch position, people before you, waiting time, and status update by polling.
8. Cancel the ticket while it is still `waiting`.

## Business Dashboard Demo Flow
1. Open `/dashboard/1`.
2. Review current customer, waiting tickets, completed tickets, cancelled tickets, absent tickets, and average wait.
3. Click `Call next customer`.
4. Update ticket status to `in_service`, `completed`, `cancelled`, or `absent`.
5. Open service management to add, edit, or delete services.
6. Open the QR page to generate the business QR code.

## Queue Logic
Ticket numbers are generated per business using `A001`, `A002`, and so on.

Active queue statuses are:

- `waiting`
- `called`
- `in_service`

Final statuses are:

- `completed`
- `cancelled`
- `absent`

Position and estimated waiting time count active tickets before the customer. Completed, cancelled, and absent tickets are removed from active queue calculations.

## QR Code Notes
QR images are generated into `qr_codes/` and served by Flask at `/qr_codes/<file>`. Generated PNG files are ignored by git. The QR destination is the public business page using `PUBLIC_BASE_URL`.

Local QR links only work from a phone if the phone can reach the computer running Flask.

## Database Reset
Stop the app, delete the SQLite file, then restart:

```bash
rm instance/noubti.db
python app.py
```

On Windows PowerShell:

```powershell
Remove-Item .\instance\noubti.db
python app.py
```

## Tests
Run:

```bash
pytest
```

The tests use a temporary database and do not modify `instance/noubti.db`.

## Troubleshooting
- `ModuleNotFoundError`: activate the virtual environment and run `pip install -r requirements.txt`.
- QR image missing: open `/business/1/qr` to generate it.
- Phone cannot scan local QR link: set `PUBLIC_BASE_URL` to your computer LAN IP and restart the app.
- Database looks stale after schema changes: stop Flask and reset `instance/noubti.db`.
- Port already in use: stop the other server or change the port in `app.py`.

## Current Limitations
- No authentication is included; the dashboard URL is public in this learning prototype.
- Overnight opening schedules are not supported.
- Polling is used instead of WebSockets.
- Notifications are in-app only.

## Future Improvements
- Owner login
- Multiple service stations
- Soft-delete services
- Better phone validation by country
- Exportable daily reports
