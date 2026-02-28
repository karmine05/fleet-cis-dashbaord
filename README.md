# Fleet CIS Compliance Dashboard 🛡️

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue?logo=docker)](https://www.docker.com/)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://www.python.org/)

**Compliance doesn't have to be a black box.** 

This dashboard transforms dry security benchmarks into a living, breathing view of your fleet's health. By connecting **CIS Controls v8.1** with **MITRE ATT&CK** and **D3FEND**, we help you move beyond "checking boxes" to actually understanding your defensive posture in real-time.

---

## 📋 What you'll need

Before diving in, make sure your Fleet instance is running the supported policies. Currently, we've optimized this dashboard for these specific CIS 8.1 benchmarks from the [fleet_policies](https://github.com/karmine05/fleet_policies) repo:

*   **macOS 26.x**: [CIS-8.1/macOS26](https://github.com/karmine05/fleet_policies/tree/main/CIS-8.1/macOS26)
*   **Windows 11**: [CIS-8.1/win11/intune](https://github.com/karmine05/fleet_policies/tree/main/CIS-8.1/win11/intune)
*   **ubuntu 24.04**: [CIS-8.1/ubuntu24](https://github.com/karmine05/fleet_policies/blob/main/CIS-8.1/ubuntu24/24.04)

---

## 🚀 Get started in 5 minutes

Everything is packed into neat containers so you can get up and running without wrestling with dependencies.

### 1. Tell the app where your Fleet is
Open `docker-compose.yml` and drop in your credentials under the `backend` and `sync` services:

```yaml
environment:
  - FLEET_URL=https://your-fleet-instance.com
  - FLEET_API_TOKEN=your-secret-token
```

### 2. Fire it up
Run this in your terminal:
```bash
docker-compose up -d --build
```

### 3. Take a look!
Head over to [http://localhost:8081](http://localhost:8081) and start exploring your data.

---

## ✨ Features we love

### 🗺️ Context is King
Standard audits tell you *what* failed. We tell you *why it matters*.
*   **MITRE ATT&CK**: See exactly which adversary techniques you're leaving the door open for.
*   **D3FEND**: Get actionable defensive techniques to close those gaps.

### 🏛️ Views for everyone
*   **The Summary**: Fast stats for the daily pulse.
*   **Security Architecture**: An interactive matrix that turns compliance into a map.
*   **Compliance Audit**: The "to-do list" with clear remediation steps.
*   **Executive Strategy**: Simplified views to help leaders make informed decisions.

---

## � Safe by Design

We take the security of your security tools seriously. Under the hood, this project is built with hardening in mind:
- **No Root Allowed**: The backend runs as a non-privileged `appuser`, so even in the worst-case scenario, the blast radius is strictly limited.
- **Isolated Services**: Your frontend and backend live in separate "rooms" (containers), meaning they can't peek into each other's business.
- **Nginx at the Helm**: We use a battle-tested Nginx server to handle your traffic, providing a much safer layer than standard development servers.
- **Granular CORS Control**: The API is not a free-for-all. You can restrict which domains are allowed to talk to your backend.
  - 💡 **Pro-tip**: Control allowed cross-origin domains by setting the `ALLOWED_ORIGINS` variable in your `docker-compose.yml`:
    ```yaml
    backend:
      environment:
        - ALLOWED_ORIGINS=https://dashboard.yourdomain.com,http://localhost:8081
    ```

---

## ⚙️ How it works

The dashboard is built on a simple, reliable stack:

| Part | Tech | Role |
| :--- | :--- | :--- |
| **The Face** | Nginx | Serves the UI and keeps API requests secure. |
| **The Brain** | Flask / Gunicorn | Handles logic and serves data (Python 3.11). |
| **The Scout** | Sync Daemon | Quietly talks to Fleet every 15 minutes to fetch updates. |
| **The Memory** | PostgreSQL 16 | Keeps a persistent record of your compliance history. |
| **The Helper** | Redis 7 | Keeps things snappy with smart caching. |

---

## � Where everything lives

If you're looking to tweak things, here's the lay of the land:

```text
fleet-cis-dashboard/
├── backend/            # The Brains (API & Data Sync)
│   ├── app.py          # Where the API starts
│   ├── sync_daemon.py  # The background worker
│   └── cis_to_d3fend.csv # The "Magic Map" between frameworks
├── frontend/           # The Face (UI Logic)
│   ├── index.html      # The main page
│   └── app.js          # The charts and interactive bits
├── Dockerfile.backend  # Instructions for building the backend
├── Dockerfile.frontend # Instructions for building the frontend
└── docker-compose.yml  # The orchestrator that ties it all together
```

---

## 🔄 Keeping data fresh

The **Sync Daemon** runs in the background every 15 minutes. If you want to see what it's doing, you can watch the logs:
```bash
docker-compose logs -f sync
```

Need data **right now**? Force an immediate update with:
```bash
docker-compose exec sync python backend/sync_fleet_data.py
```

---

## ⚖️ License

This project is open-source and available under the MIT License. Feel free to use, modify, and share!
