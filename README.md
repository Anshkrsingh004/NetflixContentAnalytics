# 🎬 Netflix Content Analytics Platform

> A production-style Business Intelligence platform that analyzes Netflix's
> global content library and turns it into executive-ready insights —
> built with Python, SQL (SQLite), Pandas, Plotly, and Streamlit.

<!-- Badges (activated once the repo is public / deployed) -->
![Python](https://img.shields.io/badge/Python-3.12-blue)
![Status](https://img.shields.io/badge/status-in%20development-orange)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 📌 Overview

This project analyzes ~8,800 Netflix titles to answer real business questions:
what kind of content is growing, which countries and genres dominate, how the
catalog has evolved over time, and which titles are similar to one another. It
is designed to look and behave like an internal analytics tool built by a data
team — not a tutorial notebook.

**What it demonstrates:** data engineering, data cleaning, SQL analytics,
exploratory data analysis, KPI design, data visualization, a content-based
recommendation engine, natural-language search, and an interactive dashboard.

> 🚧 **Status:** In active development, built milestone by milestone.
> This README grows with the project.

---

## 🧰 Tech Stack

| Layer            | Tools                                             |
|------------------|---------------------------------------------------|
| Language         | Python 3.12, SQL                                  |
| Data wrangling   | Pandas, NumPy                                      |
| Database         | SQLite (`sqlite3` standard library)               |
| Visualization    | Plotly, Matplotlib                                |
| Dashboard        | Streamlit                                          |
| ML / NLP         | scikit-learn (TF-IDF + cosine similarity)         |
| Tooling          | Jupyter, pytest, Git/GitHub, VS Code              |

---

## 📁 Project Structure

```
NetflixContentAnalytics/
├── data/
│   ├── raw/            # Original dataset (netflix_titles.csv)
│   ├── processed/      # Cleaned dataset (generated)
│   └── database/       # SQLite database (generated)
├── notebooks/          # Jupyter notebooks for EDA
├── sql/                # Schema + analytical SQL queries
├── src/
│   ├── config.py       # Central paths & constants (single source of truth)
│   ├── logger.py       # Reusable logging setup
│   ├── cleaning/       # Data-cleaning pipeline
│   ├── analysis/       # KPIs & analytical logic
│   ├── visualization/  # Reusable Plotly charts
│   └── dashboard/      # Streamlit app
├── assets/             # Images, screenshots, static files
├── tests/              # pytest test suite
├── logs/               # Runtime logs (generated)
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd NetflixContentAnalytics
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Verify the setup
```bash
python -m src.config     # prints resolved paths and confirms the dataset exists
python -m src.logger     # writes a test line to logs/netflix_analytics.log
```

---

## 🗺️ Roadmap

The platform is built in milestones. Completed items are checked off.

- [x] **M1 — Project Setup & Environment**
- [x] **M2 — Data Acquisition & Understanding**
- [x] **M3 — Data Cleaning Pipeline**
- [x] **M4 — Data Quality Report**
- [x] **M5 — Database Design & ETL**
- [x] **M6 — SQL Analytics Layer**
- [x] **M7 — Exploratory Data Analysis**
- [x] **M8 — KPI & Metrics Engine**
- [ ] **M9 — Visualization Library**
- [ ] **M10 — Recommendation Engine**
- [ ] **M11 — Natural Language Search**
- [ ] **M12 — Automated Insight Generation**
- [ ] **M13 — Streamlit Dashboard (Core)**
- [ ] **M14 — Advanced Dashboard Features**
- [ ] **M15 — Testing**
- [ ] **M16 — Documentation**
- [ ] **M17 — Deployment**
- [ ] **M18 — Interview Prep & Portfolio Polish**

---

## 📊 Data Source

*Netflix Movies and TV Shows* dataset (`netflix_titles.csv`) — publicly
available on Kaggle. Columns: `show_id, type, title, director, cast, country,
date_added, release_year, rating, duration, listed_in, description`.

---

## 🖼️ Screenshots

_Dashboard screenshots will be added once the Streamlit app is built (M13–M14)._

---

## 📄 License

Released under the MIT License. See [`LICENSE`](LICENSE) (added in M16).

---

## 🙌 Contributing

Contribution guidelines will be added in the documentation milestone (M16).
