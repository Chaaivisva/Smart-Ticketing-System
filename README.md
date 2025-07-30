# Smart Ticketing System

A robust and intelligent Django-based web application designed to streamline customer support operations through smart automation, AI-powered prioritization, and comprehensive analytics.

---

## Features

- User Authentication & Roles  
  Secure login/registration system with distinct roles: Customers, Agents, and Administrators.

- Comprehensive Ticket Management  
  - Customers can create tickets with detailed descriptions.  
  - Agents can update priority/status and add comments.  
  - Admins have full CRUD control.

- Interactive Comment System  
  Threaded communication between customers and agents, maintaining complete ticket history.

- AI-Powered Priority Assignment  
  Uses Natural Language Processing (via simulated Google Gemini API) to assign priorities automatically.

- Weighted Agent Assignment  
  Smart distribution of new tickets based on current agent workload and a configurable cap.

- Service Level Agreement (SLA) Tracking  
  - Auto-generated response_due_at and resolution_due_at timestamps.  
  - Visual alerts for SLA breaches.

- SLA Escalation (Background Task)  
  Periodic Celery task to escalate overdue tickets and log internal comments.

- Automated Reassignment of Unassigned Tickets  
  Celery Beat task to assign unassigned tickets when agents become available.

- Customer-Driven Reopening  
  Users can reopen resolved tickets by comment or explicit action.

- Admin Analytics Dashboards  
  - Agent performance metrics  
  - Ticket trends and status/priority distributions with Chart.js

---

## Technologies Used

| Component           | Stack                                       |
|---------------------|---------------------------------------------|
| Backend             | Django, Python 3.x                          |
| Database            | PostgreSQL (production), SQLite (dev)      |
| Task Queue          | Celery, Redis                               |
| Web Server          | Gunicorn                                    |
| Static Files        | Whitenoise                                  |
| Frontend            | HTML, Tailwind CSS, Chart.js                |
| AI API Integration  | Google Gemini API (simulated)               |
| Environment Manager | python-dotenv                               |

---

## Local Setup and Running

### Prerequisites

- Python 3.8+
- pip
- git
- Redis server (running locally)

### Steps

1. Clone the Repository

    git clone https://github.com/Chaaivisva/smart-ticketing-system.git  
    cd smart-ticketing-system

2. Create and Activate a Virtual Environment

    python3 -m venv .venv  
    source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate

3. Install Dependencies

    pip install -r requirements.txt

4. Configure .env File

Create a .env file in the root directory:

    SECRET_KEY='your_super_secret_key'  
    DEBUG_VALUE='True'  
    ALLOWED_HOSTS='localhost,127.0.0.1'  
    REDIS_URL="redis://localhost:6379/0"  

    # Optional for local PostgreSQL:  
    # DATABASE_URL="postgres://user:password@localhost:5432/your_database"

5. Run Migrations

    python manage.py makemigrations tickets  
    python manage.py migrate

6. Create a Superuser

    python manage.py createsuperuser

7. Create Agent User for Testing

Use the Django admin panel to create a user with role "agent".

8. Run All Services in Separate Terminals

Terminal 1:

    redis-server

Terminal 2:

    source .venv/bin/activate  
    celery -A smart_ticket worker -l info

Terminal 3:

    source .venv/bin/activate  
    celery -A smart_ticket beat -l info

Terminal 4:

    source .venv/bin/activate  
    python manage.py runserver

---

## Deployment on Render.com

1. Create PostgreSQL and Redis instances in Render Dashboard

2. Create Web Service (Main Django App)

- Build Command:

    pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate

- Start Command:

    gunicorn smart_ticket.wsgi:application

3. Set Environment Variables:

    SECRET_KEY=your_secure_key  
    DEBUG_VALUE=False  
    ALLOWED_HOSTS=your_render_url  
    DATABASE_URL=render_postgres_internal_url  
    REDIS_URL=render_redis_internal_url

4. Create Background Workers

- Celery Worker:

    celery -A smart_ticket worker -l info

- Celery Beat:

    celery -A smart_ticket beat -l info

---

## Contributing

Feel free to fork the repository, open issues, and submit pull requests.

