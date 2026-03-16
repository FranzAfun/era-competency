# ERA Competency

Internal competency assessment platform for ERA AXIS executives.

## Overview

ERA Competency is a lightweight web application used to evaluate the knowledge and competency of ERA AXIS executives through structured question and answer assessments.

The system allows the organization to serialize questions, present them to executives, collect responses, and review performance.

The entire platform is built using **Django** and runs as a **self-contained application** where the frontend, backend, and database are managed within the same environment.

## Technology Stack

* Django
* SQLite (default Django database)
* HTML / CSS (Django templates)
* JavaScript (minimal usage where required)

## Architecture

The platform is intentionally designed to remain simple:

* Backend: Django
* Frontend: Django Templates
* Database: SQLite
* Deployment: Single Virtual Machine

This avoids the complexity of a split architecture (e.g., React frontend + API backend).

## Core Features (Planned)

* Executive authentication
* Serialized competency questions
* Answer submission
* Performance evaluation
* Administrative question management
* Reporting dashboard

## Project Structure

```
era-competency/
│
├── core/              # Django project configuration
├── manage.py
├── requirements.txt
└── README.md
```

Additional Django apps will be introduced as the system evolves.

## Development Setup

Create virtual environment:

```
python -m venv venv
```

Activate environment:

Windows

```
venv\Scripts\activate
```

Install dependencies:

```
pip install -r requirements.txt
```

Run migrations:

```
python manage.py migrate
```

Start development server:

```
python manage.py runserver
```

Open:

```
http://127.0.0.1:8000
```

## Deployment

The system is intended to be deployed on a **single virtual machine**, hosting:

* Django application
* SQLite database
* Static files

This keeps infrastructure minimal and manageable.

## License

Internal ERA AXIS project.
