# Fleet CIS Compliance Dashboard

A production-ready, real-time compliance monitoring dashboard for Fleet endpoints with CIS Controls v8.1 benchmarks, D3FEND/MITRE ATT&CK mapping, and executive strategy views.

## Quick Start

```bash
./start.sh
# Dashboard: http://localhost:8000
# API: http://localhost:5001
```

## Features

### 📊 Dashboard Views

1. **Summary** - KPIs, compliance donut, policy distribution, safeguard heatmap
2. **Security Architecture** - D3FEND/MITRE ATT&CK matrix, technique mapping, gap analysis
3. **Compliance Audit** - Two-column policy list with descriptions, resolutions, SQL queries
4. **Executive Strategy** - CISO command center with posture gauge, roadmap, team leaderboard

### 🔍 Filtering

- **Teams**: Filter by Fleet teams
- **Platforms**: Windows, macOS, Linux
- **Labels**: Dynamic labels from Fleet (replaces static device types)
- **OS Versions**: Platform-specific versions

### 📈 Metrics

- Security Posture Score (0-100)
- Compliance Coverage
- Risk Exposure
- Remediation Velocity
- Framework Alignment (CIS, NIST, ISO)
- **MITRE ATT&CK Matrix** with real-time defensive coverage

## 🧠 Core System Logic

This dashboard implements several advanced security analysis layers on top of raw Fleet data.

### 🛡️ MITRE ATT&CK & D3FEND Mapping
Compliance safeguards are provided with defensive context by mapping them to the MITRE ATT&CK and D3FEND frameworks.
- **Mapping Data**: `backend/cis_to_d3fend.csv` maps CIS Safeguard IDs to D3FEND Techniques and MITRE ATT&CK IDs.
- **Dynamic Matrix**: The "Security Architecture" tab generates a MITRE matrix by joining Fleet policy results with this mapping, categorized into Tactics (Reconnaissance, Execution, etc.) via a lookup table in the backend.

### 🏷️ MITRE ATT&CK Tactic Key
The dashboard uses the following two-letter abbreviations for MITRE ATT&CK tactics in the Security Architecture views:

| Code | Tactic | Description |
|:---:|:---|:---|
| **RC** | Reconnaissance | Information gathering for attack planning |
| **RD** | Resource Development | Building infrastructure (accounts, servers, etc.) |
| **IA** | Initial Access | Initial entry into the environment |
| **EX** | Execution | Running malicious code or commands |
| **PE** | Persistence | Maintaining access across reboots or service restarts |
| **PR** | Privilege Escalation | Gaining higher-level permissions (Admin/Root) |
| **DE** | Defense Evasion | Avoiding detection and bypassing security controls |
| **CA** | Credential Access | Stealing account names and passwords (MFA, Keychain) |
| **DI** | Discovery | Exploring the environment to find targets and data |
| **LM** | Lateral Movement | Moving between systems within the internal network |
| **CO** | Collection | Gathering sensitive data for intended exfiltration |
| **C2** | Command & Control | Communicating with compromised systems |
| **EF** | Exfiltration | Stealing data from the environment |
| **IM** | Impact | Disrupting, destroying, or altering system integrity |

### 🎯 Prioritization Logic (Impact vs. Effort)
The "Executive Strategy" tab automatically prioritizes remediation using a heuristic matrix:
- **Impact**: Classified as **High** (>5 failing hosts), **Medium** (>2 failing hosts), or **Low** based on blast radius.
- **Effort**: Classified as **Low** (automated configuration checks like "Ensure..."), **Medium** (standard settings), or **High** (manual audits/reviews).

### 📈 Trend Analysis & Data Synchronization
- **Daily Snapshots**: The `sync_fleet_data.py` script creates daily records in the `compliance_snapshots` table. This allows the "Executive Strategy" roadmap to show real historical progress.
- **Data Sync**: Uses parallel `ThreadPoolExecutor` workers to fetch results from the Fleet API efficiently, even for large environments.
- **Trend Detection**: Calculates week-over-week gains and losses by comparing current results against historical check timestamps.

### ⚙️ User-Configurable Weights
All scoring parameters can be customized via the Settings tab:

| Parameter | Default | Description |
|-----------|---------|-------------|
| Impact High Threshold | 5 | Fails > this = High impact |
| Impact Medium Threshold | 2 | Fails > this = Medium impact |
| Low Effort Keywords | Ensure, Set | Policy name keywords for low effort |
| High Effort Keywords | Manual, Review | Policy name keywords for high effort |
| Risk Multiplier | 2 | fail_count × this for risk exposure |
| Security Debt | 0.5h | Hours of debt per failing policy |
| CIS Alignment | 0.95 | posture × this for CIS score |
| NIST Alignment | 0.88 | posture × this for NIST score |
| ISO Alignment | 0.82 | posture × this for ISO score |

## Architecture


```
fleet-cis-dashboard/
├── backend/
│   ├── app.py              # Flask REST API
│   ├── schema.sql          # SQLite database schema
│   ├── sync_fleet_data.py  # Fleet API sync script
│   ├── cis_to_d3fend.csv   # CIS to D3FEND/MITRE mapping
│   └── compliance.db       # SQLite database
├── frontend/
│   ├── index.html          # Dashboard UI
│   ├── app.js              # JavaScript logic
│   └── styles.css          # Premium styling
├── start.sh                # Start script
└── stop.sh                 # Stop script
```

## Setup

### Prerequisites
- Python 3.8+
- Fleet API token (for real data sync)

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
cd backend && python reinit_db.py

# Sync data from Fleet (requires FLEET_TOKEN env var)
export FLEET_URL=https://your-fleet-instance.com
export FLEET_TOKEN=your-api-token
python sync_fleet_data.py

# Start dashboard
cd .. && ./start.sh
```

### Docker

```bash
docker-compose up
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/teams` | List all teams |
| `/api/platforms` | List all platforms |
| `/api/labels` | List all host labels |
| `/api/devices` | Get filtered devices |
| `/api/compliance-summary` | Compliance metrics |
| `/api/safeguard-compliance` | Per-safeguard compliance |
| `/api/heatmap-data` | D3FEND heatmap data |
| `/api/architecture` | Security architecture metrics |
| `/api/audit` | Audit policy details |
| `/api/strategy` | Executive strategy metrics |

### Query Parameters
All endpoints support: `team`, `platform`, `label`, `osVersion`

## Database Schema

- `fleet_hosts` - Host information synced from Fleet
- `fleet_teams` - Team definitions
- `cis_policies` - CIS policy definitions with descriptions/resolutions
- `policy_results` - Policy pass/fail results per host
- `fleet_labels` - Label definitions from Fleet
- `host_labels` - Host-to-label associations

## Data Sources

### Real Data (Production)
Set environment variables and run `sync_fleet_data.py`:
- Syncs hosts, teams, policies, and labels from Fleet API.
- **Automatic Snapshots**: Each sync generates a daily snapshot in `compliance_snapshots` for trend reporting.
- **Parallel Processing**: Results are fetched in parallel to optimize for large fleets.

### Notes on Simulated Data
While the core logic is implemented, some historical metrics may show simulated values if `compliance_snapshots` or `policy_results` history is insufficient (e.g. less than 50 days of data).
- **Roadmap projections** - Uses a combination of real snapshots and target trajectories.
- **Team trends** - Calculates changes based on available records.

## Browser Support

- Chrome 90+ / Firefox 88+ / Safari 14+ / Edge 90+

## License

MIT License
