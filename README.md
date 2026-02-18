# Fleet CIS Compliance Dashboard 🛡️

A production-ready, real-time compliance monitoring dashboard for Fleet endpoints. This project provides deep visibility into CIS Controls v8.1 benchmarks, D3FEND/MITRE ATT&CK mapping, and executive strategy metrics.

## 🚀 Quick Start (Recommended)

The entire stack is containerized for production parity.

```bash
# 1. Start the full stack
docker-compose up -d --build

# 2. Access the Dashboard
# Port 8081 (default)
http://localhost:8081
```

### Services Included:
- **Frontend**: Nginx (Static UI + API Proxy)
- **Backend**: Gunicorn + Flask API (Python 3.12)
- **Database**: PostgreSQL 16
- **Cache**: Redis 7

---

## ⚙️ Configuration

### Environment Variables
Environment variables are managed directly within the `docker-compose.yml` file under the `backend` service. 

**Required Keys:**
- `FLEET_URL`: The URL of your Fleet instance.
- `FLEET_API_TOKEN`: Valid Fleet API token for data synchronization.

> [!NOTE]
> The `.env` file is no longer used to simplify container management. Modify `docker-compose.yml` directly for configuration changes.

---

## 📊 Feature Highlights

### 🛡️ Framework Mapping (MITRE & D3FEND)
Unlike standard compliance tools, this dashboard maps CIS Safeguards to defensive frameworks:
- **Data Source**: `backend/cis_to_d3fend.csv`
- **Logic**: Joins Fleet policy results with MITRE ATT&CK IDs and D3FEND Techniques to visualize defensive coverage.

### 🏛️ Dashboard Views
1.  **Summary**: Real-time KPI cards and safeguard heatmaps.
2.  **Security Architecture**: Interactive MITRE/D3FEND matrix showing compliant vs. non-compliant coverage.
3.  **Compliance Audit**: Detailed breakdown of failing policies with remediation SQL.
4.  **Executive Strategy**: CISO-level overview with posture scores, roadmap, and team leaderboard.

---

## 📁 Project Structure

```text
fleet-cis-dashboard/
├── backend/            # Flask API & Data Sync Logic
│   ├── app.py          # API Entry Point
│   ├── db.py           # Postgres Logic
│   └── cis_to_d3fend.csv # Framework Mappings
├── frontend/           # Static User Interface
│   ├── index.html      # Main Dashboard
│   └── app.js          # UI Logic & Visualization
├── nginx.conf          # Nginx Proxy Configuration
├── Dockerfile          # Backend Container Definition
└── docker-compose.yml  # Orchestration & Environment
```

---

## 🛠️ Data Synchronization
The backend automatically handles data ingestion from Fleet. If you need to manually trigger a sync from within the container:

```bash
docker-compose exec backend python sync_fleet_data.py
```

## ⚖️ License
MIT License
