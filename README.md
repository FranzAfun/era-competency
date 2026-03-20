# ERA Competency

ERA Competency is a completed internal assessment platform for ERA AXIS executives.

## Project Status

The platform is feature-complete for the current scope and is ready for production deployment on a single VM.

## What The System Does

- Executive login with OTP verification
- Stage-based assessments (4 stages, 25 questions per stage)
- Instant answer feedback and stage result scoring
- Historical dashboard for executive progress
- Admin portal for stage and question management
- Question CRUD support (create, bulk upload, update, bulk delete)
- Admin notifications when an executive completes Stage 4 (pass or fail)

## Technology Stack

- Django
- SQLite (default)
- Django templates (HTML/CSS)
- Vanilla JavaScript (UI interactions)

## Architecture

- Backend: Django
- Frontend: Django Templates
- Database: SQLite
- Deployment model: Single VM (Gunicorn + Nginx + systemd)

## Local Development Setup

1. Create a virtual environment.

```bash
python -m venv venv
```

2. Activate it.

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

3. Install dependencies.

```bash
pip install -r requirements.txt
```

4. Apply migrations.

```bash
python manage.py migrate
```

5. Run the application.

```bash
python manage.py runserver
```

6. Open in browser.

```text
http://127.0.0.1:8000
```

## Main Routes

- Executive login: /login/
- Executive dashboard: /dashboard/
- Assessment: /assessment/
- Admin portal login: /portal/login/
- Admin portal dashboard: /portal/

## Deployment

For production deployment on GCP VM, follow:

- DEPLOYMENT_GCP_VM.md

Recommended pre-production checks:

```bash
python manage.py check --deploy
python manage.py collectstatic --noinput
```

## License

Internal ERA AXIS project.
