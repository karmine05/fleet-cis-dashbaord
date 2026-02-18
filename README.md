# Fleet CIS Compliance Dashboard 🛡️

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue?logo=docker)](https://www.docker.com/)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://www.python.org/)

A production-ready, real-time compliance monitoring dashboard for Fleet endpoints. This project provides deep visibility into **CIS Controls v8.1** benchmarks, **MITRE ATT&CK** mappings, and **D3FEND** defensive techniques.

---

## 🚀 Quick Start

The entire stack is containerized for production parity and easy deployment.

### 1. Configure Credentials
Open `docker-compose.yml` and set your Fleet credentials in the `backend` and `sync` services:

```yaml
environment:
  - FLEET_URL=https://your-fleet-instance.com
  - FLEET_API_TOKEN=your-secret-token
```

### 2. Launch the Stack
```bash
docker-compose up -d --build
```

### 3. Access the Dashboard
Navigate to `http://localhost:8081` in your browser.

---

## 🏗️ Architecture & Services

The dashboard runs as a multi-container application orchestrated by Docker Compose:

| Service | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | Nginx | Serves the static UI and proxies API requests. |
| **Backend** | Flask / Gunicorn | Handles API requests and logic (Python 3.11). |
| **Sync Daemon** | Python | Periodically ingests data from your Fleet instance. |
| **Database** | PostgreSQL 16 | Persistent storage for compliance data and history. |
| **Cache** | Redis 7 | Used for performance optimization and session management. |

---

## 📊 Key Features

### 🛡️ Framework Mapping
Unlike standard compliance tools, this dashboard maps CIS Safeguards directly to defensive frameworks:
- **MITRE ATT&CK**: Visualize defensive coverage against specific adversary tactics.
- **D3FEND**: Identify technical countermeasures associated with each safeguard.
- **Data Source**: Mappings are maintained in `backend/cis_to_d3fend.csv`.

### 🏛️ Dashboard Views
1.  **Summary**: High-level posture scores, KPI cards, and safeguard heatmaps.
2.  **Security Architecture**: Interactive MITRE/D3FEND matrix showing compliant vs. non-compliant coverage.
3.  **Compliance Audit**: Granular view of failing policies with remediation guidance.
4.  **Executive Strategy**: CISO-level overview with roadmap projections and team leaderboards.

---

## 📁 Project Structure

```text
fleet-cis-dashboard/
├── backend/            # Python API & Data Ingestion
│   ├── app.py          # Flask API Entry Point
│   ├── sync_daemon.py  # Periodic Sync Process
│   ├── db.py           # Database Interface
│   └── cis_to_d3fend.csv # Framework Mappings
├── frontend/           # Web Interface
│   ├── index.html      # Main Dashboard
│   └── app.js          # UI Logic & Visualizations
├── nginx.conf          # Nginx Reverse Proxy Config
├── Dockerfile          # Backend/Sync Container Image
└── docker-compose.yml  # System Orchestration
```

---

## 🛠️ Data Synchronization

The **Sync Daemon** runs automatically every 15 minutes (configurable via `SYNC_INTERVAL_MINUTES`). 

To monitor synchronization status:
```bash
docker-compose logs -f sync
```

To manually trigger an immediate sync:
```bash
docker-compose exec sync python backend/sync_fleet_data.py
```

---

## ⚖️ License

Distributed under the MIT License. See `LICENSE` (if available) for more information.
