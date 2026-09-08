# 🤝 Contributing Guide — Terre‑Vent‑Feu‑Eau

Thank you for contributing to **Terre‑Vent‑Feu‑Eau**, a data and machine learning platform for wildfire analysis, visualization, and risk prediction.  
This document explains how to collaborate effectively, how to use the Gitflow workflow, how to create branches, how to submit Pull Requests, and how to comply with CI/CD and code quality standards.

Following these guidelines ensures a **stable**, **secure**, **high‑quality**, and **professional** project.

---

# 📐 Git Workflow — Gitflow

The project uses a structured Gitflow workflow.

## 🌱 Main Branches

### `main`
- Stable production-ready code  
- Protected branch  
- CI checks required  
- Automatic version tagging  
- No direct pushes allowed  

### `develop`
- Integration branch  
- All features are merged here  
- CI checks required  

---

## 🌿 Feature Branches

All new work must be done in branches following this naming convention:



Examples:

feature/sql-schema
feature/ingestion-pipeline
feature/streamlit-ui
feature/model-training
feature/eda
feature/documentation


---

# 🛠️ Creating a Feature Branch

Always start from `develop`:

```bash
git checkout develop
git pull
git checkout -b feature/<name>
```
---

# 📤 Pushing Your Work

```bash
git push origin feature/<name>
```
---

# 🔁 Pull Requests (PR)

Pull Requests are mandatory for all changes.

✔ PR to develop
Used for integrating new features.

Steps:

Open a PR:
feature/<name> → develop

Ensure CI passes

Fix issues if needed

Request a review

Merge only if:

CI = OK

Review = OK

🚀 PR to main
Used for stable releases.

Steps:

Open a PR:
develop → main

CI must pass

Review required

Merge allowed

Automatic version tag is created (via versioning workflow)
