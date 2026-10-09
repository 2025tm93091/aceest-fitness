# ACEest Fitness & Gym — DevOps CI/CD Pipeline

![CI](https://github.com/2025tm93091/aceest-fitness/actions/workflows/main.yml/badge.svg)

A Flask-based REST API for the ACEest Fitness & Gym management system, with a fully automated CI/CD pipeline built using **GitHub Actions** and **Jenkins**, containerized with **Docker**, and validated by **56 pytest cases** with 97% code coverage.

> **Course:** Introduction to DevOps (CSIZG514/SEZG514)  
> **Assignment:** 1 — Implementing Automated CI/CD Pipelines  
> **Student:** Bhanu Prakash (2025tm93091)  
> **Institution:** BITS Pilani — WILP

---

## 📋 Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Local Setup & Execution](#local-setup--execution)
- [Running Tests Manually](#running-tests-manually)
- [Docker Usage](#docker-usage)
- [CI/CD Pipeline Architecture](#cicd-pipeline-architecture)
  - [GitHub Actions](#github-actions)
  - [Jenkins](#jenkins)
- [API Endpoints](#api-endpoints)
- [Author](#author)

---

## Overview

ACEest Fitness & Gym is a rapidly scaling startup that requires a **robust, automated deployment workflow**. This project implements:

1. **Modularized Flask application** — business logic (`core.py`), persistence (`db.py`), PDF reporting (`report.py`), and HTTP routes (`app.py`) cleanly separated.
2. **Comprehensive test suite** — 56 pytest cases across all modules with **97% aggregate coverage**.
3. **Containerization** — single Docker image with multi-stage efficiency, non-root user, and health check.
4. **Automated CI** — GitHub Actions runs on every push.
5. **On-prem CI/CD** — Jenkins pipeline runs the full build → test → deploy workflow inside a Docker container.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.14 |
| Web framework | Flask 3.0 |
| Database | SQLite 3 (bundled) |
| PDF generation | fpdf2 2.7.9 |
| Testing | pytest 8.3, pytest-cov 5.0 |
| Linting | flake8 7.1 |
| Containerization | Docker 27.5 |
| CI/CD | GitHub Actions, Jenkins 2.568 |
| Version control | Git / GitHub |

---

## Project Structure
aceest-fitness/
├── .github/
│ └── workflows/
│ └── main.yml # GitHub Actions CI/CD workflow
├── .dockerignore # Docker build context exclusions
├── .gitignore # Git exclusions
├── Dockerfile # Production container definition
├── Jenkinsfile # Jenkins declarative pipeline
├── README.md # This file
├── app.py # Flask routes (HTTP layer)
├── core.py # Business logic (BMI, calories)
├── db.py # SQLite persistence
├── report.py # PDF generation
├── requirements.txt # Python dependencies
└── test_app.py # Pytest suite (56 tests)


---

## Local Setup & Execution

### Prerequisites

- Python 3.11+ (project tested on 3.14)
- Docker Desktop (for container runs)
- Git

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/2025tm93091/aceest-fitness.git
cd aceest-fitness

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # On Windows: .\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the Flask application
python app.py
```

### Quick verification

```bash
curl http://localhost:5000/health
# {"status":"healthy"}
```

## Running Tests Manually

```bash
# Basic test run
pytest -v

# With coverage report
pytest -v --cov=core --cov=db --cov=report --cov=app --cov-report=term-missing
```

### Linting

```bash
flake8 app.py core.py db.py report.py test_app.py --max-line-length=100
```

## Docker Usage

```bash
docker build -t aceest-fitness:v1 .
docker run -d --name aceest-app -p 5000:5000 aceest-fitness:v1
docker ps                                        # Should show "(healthy)"
curl http://localhost:5000/health                # {"status":"healthy"}
docker run --rm \
  -v "$PWD:/app" -w /app \
  -e ACEEST_DB_PATH=/tmp/aceest_test.db \
  -e COVERAGE_FILE=/tmp/.coverage \
  aceest-fitness:v1 \
  sh -c "pip install pytest pytest-cov && pytest -v"

docker stop aceest-app && docker rm aceest-app
```

## CI/CD Pipeline Architecture

┌─────────────────┐
│  Developer      │
│  (Local Laptop) │
└────────┬────────┘
         │ git push
         ▼
┌─────────────────┐
│   GitHub Repo   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────────────────┐
│GitHub  │ │ Jenkins on           │
│Actions │ │ Prayogsala VM        │
│(cloud) │ │ (BITS internal)      │
└───┬────┘ └──────────┬───────────┘
    │                 │
    │ runs on         │ runs on
    │ Ubuntu runner   │ VM with Docker
    ▼                 ▼
✅ Lint              ✅ Checkout
✅ Test (56)         ✅ Docker Build
✅ Docker Build      ✅ Test in Container
✅ Health Check      ✅ Lint
                     ✅ Deploy (port 5000)
```

### GitHub Actions

Workflow file: [.github/workflows/main.yml](.github/workflows/main.yml)

Triggers: Push to main/develop, PRs to main

Jobs:

Lint & Test — Sets up Python 3.14, installs dependencies, runs flake8 and pytest --cov.

Docker Build & Smoke Test — Builds the Docker image, runs pytest inside the container with mounted volume, verifies /health endpoint.

### Jenkins

Pipeline file: [Jenkinsfile](Jenkinsfile) (declarative pipeline)

Server: Jenkins 2.568.1 on Prayogsala VM (BITS internal)
Trigger: Manual "Build Now" (can be extended with GitHub webhook)

Stages:

Checkout — Clones the repository from GitHub.

Build Docker Image — Builds aceest-fitness:build-${BUILD_NUMBER}.

Run Tests in Container — Runs pytest inside the container with the workspace mounted and coverage output redirected to /tmp (writable).

Lint — Runs flake8 inside the container.

Deploy — Stops any existing aceest-app container, runs the new image on port 5000, and verifies /health.

Design notes:

Jenkins user is added to the docker group (GID 981) so docker build/run work without sudo.

Coverage and test DB paths are redirected to /tmp to avoid permission issues on the read-only mounted workspace.

Old images are pruned in the post block to keep the VM clean.

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Service info |
| GET | `/health` | Health check (used by Docker HEALTHCHECK) |
| GET | `/programs` | List available training programs |
| POST | `/calculate/calories` | Daily calorie target |
| POST | `/calculate/bmi` | BMI + category |
| GET | `/clients` | List all clients |
| POST | `/clients` | Create/update a client |
| GET | `/clients/<name>` | Get one client |
| DELETE | `/clients/<name>` | Delete a client |
| GET | `/clients/<name>/progress` | Progress history |
| POST | `/clients/<name>/progress` | Log weekly adherence |
| GET | `/clients/<name>/report.pdf` | Download PDF report |
| GET | `/demo/<name>` | HTML preview of the PDF |

### Example requests

```bash
# Create a client
curl -X POST http://localhost:5000/clients \
  -H "Content-Type: application/json" \
  -d '{"name":"Alice","age":28,"height":170,"weight":65,"program":"Fat Loss (FL) - 3 day"}'

# Calculate BMI
curl -X POST http://localhost:5000/calculate/bmi \
  -H "Content-Type: application/json" \
  -d '{"weight":70,"height":175}'

# Generate PDF report
curl http://localhost:5000/clients/Alice/report.pdf -o report.pdf
```

## Author

Bhanu Prakash
M.Tech (Software Engineering) — BITS Pilani WILP
Student ID: 2025tm93091
Email: 2025tm93091@wilp.bits-pilani.ac.in

## Acknowledgments
Assignment developed for Introduction to DevOps (SEZG514) at BITS Pilani.

Baseline application logic derived from the Tkinter versions provided in the course materials, ported to Flask as a REST API.

CI/CD infrastructure provisioned on Prayogsala — BITS Pilani's internal virtual lab platform.



