# 🧪 AI-Powered Unit Test Generator

Generate clean, accurate Python unit tests using a fine-tuned CodeT5 model.
![Project Banner](/frontend/public/Banner.png)

---

## Overview

This project is an intelligent unit-test generation engine that uses a **fine-tuned CodeT5p-220M model** to automatically produce pytest-style test cases for Python functions.

It supports multiple functions per file, regeneration with different sampling strategies, AST validation, and an interactive UI for managing test sessions.

This project is currently in **active development** and will be publicly released on:

### **📆 Expected Release: January 2026**

---

## Key Features

### ✅ AI-Driven Unit Test Generation

- Fine-tuned CodeT5p model trained on **8,465+ function→test pairs**
- Beam search + sampling for diverse test outputs
- Smart fallback mechanism for difficult functions
- Ensures all generated tests begin with `import pytest`
- AST-based validation for syntax correctness

### 🔁 Test Regeneration Engine

- Regenerate using multiple sampling strategies
- Multi-function parsing support
- Automatic format normalization

### 🖥️ Web Dashboard (React)

- Paste or upload Python code
- Generate tests instantly
- Regenerate tests with one click
- Copy, download, and manage sessions
- JWT authentication

#### UI Preview Placeholders:

![Dashboard Screenshot](/frontend/public/Dashboard.png)
_(Dashboard View)_

![Generation Screenshot](/frontend/public/Generate.png)
_(Generation View)_

![Generated-Test Screenshot](/frontend/public/Generated_Test.png)  
_(Generated Test View)_

---

## 🛠️ Tech Stack

**Backend:** Django REST Framework, Python, PyTorch, HuggingFace Transformers  
**Frontend:** React (Vite) + TanStack Query  
**AI Model:** CodeT5p-220M (Fine-tuned)  
**Database:** PostgreSQL  
**Auth:** JWT  
**Planned Deployment:** Docker + Render/Railway/AWS

---

## Project Structure

To be updated

---

## Roadmap

### 🔄 In Progress

- Improve regeneration diversity
- Expand dataset to 10k+ pairs
- Build dedicated edge-case dataset + model
- UI/UX polish

### 🗓️ Upcoming

- Full public release (January 2026)
- Public API endpoints

---

## Current Status

The project is approximately **75–80% complete**.  
Core functionality is implemented, including:

- Base test generation
- Regeneration engine
- Authentication
- UI functionality
- Dataset pipeline
- Fine-tuned model

Remaining tasks involve:

- Edge-case model training
- UI polish
- Large-scale dataset expansion
- Deployment + documentation

---

## 🤝 Contributing

This is currently a **private research project**.  
Contributions may be welcomed after initial public release.

---

## 📄 License

License information will be added before public release.

---

## ✉️ Contact

**Philip Feranmi**  
AI & Full-Stack Developer

Email: feranmiphileo@gmail.com
LinkedIn: https://pl.linkedin.com/in/akinwale-feranmi-954bb322b

---
