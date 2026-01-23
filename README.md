# AI-Powered Unit Test Generator

An intelligent web-based system for automatically generating Python unit tests using a fine-tuned CodeT5 model.

---

## Overview

This project is a **fully implemented AI-powered unit test generation system** developed as part of a **Bachelor’s Thesis in Computer Science**.

The system uses a **fine-tuned CodeT5p-220M transformer model** to generate high-quality, pytest-style unit tests for Python functions. It supports multiple functions per input, regeneration strategies, syntax validation, and a complete web interface for managing test sessions.

The application consists of:

- A Django REST backend
- A React (Vite) frontend
- A fine-tuned transformer model for test generation
- Dockerized infrastructure for reproducible execution

---

## Core Features

### AI-Based Unit Test Generation

- Fine-tuned **CodeT5p-220M** model
- Trained on **8,465+ function → test pairs**
- Generates valid pytest-style unit tests
- Ensures all outputs start with:
  ```python
  import pytest
  ```
- AST-based syntax validation to prevent invalid code
- Supports multiple functions per uploaded file or pasted input

### Test Regeneration Engine

- Regenerates tests using alternative decoding strategies
- Allows comparison of multiple outputs for the same function
- Normalizes generated tests into a consistent format

### Web Application Interface

- Paste Python code or upload .py files
- Generate tests instantly
- Regenerate tests on demand
- Copy or download generated test files
- Manage multiple test sessions
- JWT-based authentication system

---

## Technology Stack

### Backend

- Python
- Django & Django REST Framework
- PostgreSQL
- PyTorch
- Hugging Face Transformers

### Frontend

- React (Vite)
- TanStack Query

### AI Model

- CodeT5p-220M (fine-tuned)

### Authentication

- JWT (SimpleJWT)

### Infrastructure

- Docker & Docker Compose

## Project Structure

```
Thesis/
├── ai_test_generator/      # Django project configuration
├── unittestgen/            # Core backend application
├── frontend/               # React frontend (Vite)
├── docker/                 # Startup scripts
├── docker-compose.yml
├── Dockerfile
├── manage.py
├── Pipfile
├── Pipfile.lock
└── README.md
```

---

## Model & Dataset Availability

### Important Note for Reviewers

To keep the repository lightweight and suitable for academic submission:

- Fine-tuned model checkpoints
- Training datasets (JSONL files)
- Experiment logs and intermediate artifacts

are **not included** in this repository.

These components are:

- Fully described in the thesis documentation
- Referenced via Hugging Face model identifiers
- Excluded due to size constraints and submission guidelines

The application is configured to load models dynamically using public Hugging Face repositories.

### Fine-Tuned Models

The fine-tuned models used by this system are publicly available on Hugging Face:

- **Base Model (Standard Test Generation):**  
  https://huggingface.co/Oluwaferanmiii/codet5p-220m-pytest-generator

- **Edge-Case Model:**  
  https://huggingface.co/Oluwaferanmiii/codet5p-220m-pytest-edge-generator

These models are loaded dynamically at runtime and are not stored in this repository due to size constraints.

---

## Running the Application (Docker)

### Requirements

- Docker
- Docker Compose

### Build and Run

```
docker compose up --build
```

The application will be available at:

```
http://localhost:8000
```

---

## Project Status

The system is **fully implemented and functional**, including:

- AI-based test generation
- Regeneration logic
- Authentication
- Frontend UI
- Backend API
- Dockerized setup

Additional model training and dataset expansion are outside the scope of this submission and are discussed in the thesis as future work.

---

## Academic Context

This project was developed as part of a Bachelor’s thesis focused on:

**Artificial Intelligence in Software Testing**
Automated unit test generation using transformer-based language models

The repository represents the **final implementation** used for evaluation and demonstration.

---

## License

License information will be added prior to public open-source release.

---

## Contact

**Philip Feranmi Akinwale**
AI & Full-Stack Developer

📧 Email: feranmiphileo@gmail.com
🔗 LinkedIn: https://pl.linkedin.com/in/akinwale-feranmi-954bb322b
