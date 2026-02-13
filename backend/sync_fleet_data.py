import os
import sqlite3
import requests
import time
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
FLEET_URL = os.environ.get("FLEET_URL", "https://fleet.example.com")
FLEET_TOKEN = os.environ.get("FLEET_API_TOKEN", "")
DB_PATH = os.path.join(os.path.dirname(__file__), "compliance.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")
MAX_WORKERS = int(os.environ.get("SYNC_MAX_WORKERS", "10"))
HOSTS_PER_PAGE = int(os.environ.get("SYNC_HOSTS_PER_PAGE", "100"))

# CIS control regex — matches "CIS - 1.1 - ...", "CIS 1.1 ...", "1.1 ..."
CIS_REGEX = re.compile(r'(?:CIS|Benchmark)\s*[-:]?\s*(\d+(?:\.\d+)+)', re.IGNORECASE)
CIS_FALLBACK_REGEX = re.compile(r'^(\d+(?:\.\d+)+)\s')


def get_db_connection():
    """Connect to SQLite database with WAL mode for concurrent read/write."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    """Initialize database schema if tables don't exist."""
    conn = get_db_connection()
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())
    conn.close()
    print("Database schema ensured.")


def get_fleet_headers():
    return {
        "Authorization": f"Bearer {FLEET_TOKEN}",
        "Content-Type": "application/json"
    }


# ---------------------------------------------------------------------------
# Fleet API Helpers (with pagination support)
# ---------------------------------------------------------------------------

def fetch_teams():
    """Fetch teams from Fleet."""
    if not FLEET_TOKEN: return []
    try:
        url = f"{FLEET_URL}/api/v1/fleet/teams"
        response = requests.get(url, headers=get_fleet_headers(), timeout=10, verify=False)
        response.raise_for_status()
        return response.json().get("teams", [])
    except Exception as e:
        print(f"  ⚠ Error fetching teams: {e}")
        return []


def fetch_hosts_paginated():
    """Fetch all hosts from Fleet using pagination."""
    if not FLEET_TOKEN: return []
    all_hosts = []
    page = 0
    while True:
        try:
            url = f"{FLEET_URL}/api/v1/fleet/hosts?per_page={HOSTS_PER_PAGE}&page={page}"
            response = requests.get(url, headers=get_fleet_headers(), timeout=30, verify=False)
            response.raise_for_status()
            hosts = response.json().get("hosts", [])
            if not hosts:
                break
            all_hosts.extend(hosts)
            page += 1
        except Exception as e:
            print(f"  ⚠ Error fetching hosts page {page}: {e}")
            break
    return all_hosts


def fetch_labels():
    """Fetch labels from Fleet."""
    if not FLEET_TOKEN: return []
    try:
        url = f"{FLEET_URL}/api/v1/fleet/labels"
        response = requests.get(url, headers=get_fleet_headers(), timeout=10, verify=False)
        response.raise_for_status()
        return response.json().get("labels", [])
    except Exception as e:
        print(f"  ⚠ Error fetching labels: {e}")
        return []


def fetch_host_details(host_id):
    """Fetch detailed host info including labels."""
    if not FLEET_TOKEN: return None
    try:
        url = f"{FLEET_URL}/api/v1/fleet/hosts/{host_id}"
        response = requests.get(url, headers=get_fleet_headers(), timeout=10, verify=False)
        response.raise_for_status()
        return response.json().get("host", {})
    except Exception:
        return None


def fetch_version():
    """Fetch and print Fleet version."""
    if not FLEET_TOKEN: return
    try:
        url = f"{FLEET_URL}/api/v1/fleet/version"
        response = requests.get(url, headers=get_fleet_headers(), timeout=10, verify=False)
        if response.status_code == 200:
            print(f"  Fleet Version: {response.json().get('version', 'Unknown')}")
    except Exception as e:
        print(f"  ⚠ Error fetching version: {e}")


def fetch_policies(teams):
    """Fetch policies from Fleet (Global + Team-specific)."""
    if not FLEET_TOKEN: return []
    all_policies = {}

    # Global Policies
    try:
        url = f"{FLEET_URL}/api/v1/fleet/policies"
        response = requests.get(url, headers=get_fleet_headers(), timeout=10, verify=False)
        if response.status_code == 200:
            for p in response.json().get("policies", []):
                p['team_id'] = None
                all_policies[p['id']] = p
        elif response.status_code == 404:
            url = f"{FLEET_URL}/api/v1/fleet/global/policies"
            response = requests.get(url, headers=get_fleet_headers(), timeout=10, verify=False)
            if response.status_code == 200:
                for p in response.json().get("policies", []):
                    p['team_id'] = None
                    all_policies[p['id']] = p
    except Exception as e:
        print(f"  ⚠ Error fetching global policies: {e}")

    # Team Policies
    for team in teams:
        try:
            url = f"{FLEET_URL}/api/v1/fleet/teams/{team['id']}/policies"
            response = requests.get(url, headers=get_fleet_headers(), timeout=10, verify=False)
            if response.status_code == 200:
                team_policies = response.json().get("policies", [])
                for p in team_policies:
                    p['team_id'] = team['id']
                    all_policies[p['id']] = p
        except Exception as e:
            print(f"  ⚠ Error fetching policies for team {team.get('name')}: {e}")

    return list(all_policies.values())


def fetch_policy_hosts(policy_id, status):
    """Fetch hosts for a policy with specific status (passing/failing)."""
    if not FLEET_TOKEN: return []
    try:
        response_type = "passing" if status == "pass" else "failing"
        url = f"{FLEET_URL}/api/v1/fleet/hosts?policy_id={policy_id}&policy_response={response_type}"
        response = requests.get(url, headers=get_fleet_headers(), timeout=30, verify=False)
        if response.status_code == 200:
            hosts = response.json().get("hosts", [])
            return [(policy_id, h['id'], status, datetime.now().isoformat()) for h in hosts]
        return []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Sync Metadata Helpers
# ---------------------------------------------------------------------------

def start_sync_record(conn):
    """Insert a new sync_metadata row with status='running'. Returns sync_id."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sync_metadata (started_at, status) VALUES (?, 'running')",
        (datetime.now().isoformat(),)
    )
    conn.commit()
    return cursor.lastrowid


def complete_sync_record(conn, sync_id, hosts_changed, policies_changed, results_changed, start_time):
    """Finalize sync_metadata row on success."""
    duration_ms = int((time.time() - start_time) * 1000)
    conn.execute("""
        UPDATE sync_metadata
        SET completed_at = ?, status = 'success',
            hosts_changed = ?, policies_changed = ?, results_changed = ?,
            duration_ms = ?
        WHERE sync_id = ?
    """, (datetime.now().isoformat(), hosts_changed, policies_changed, results_changed, duration_ms, sync_id))
    conn.commit()


def fail_sync_record(conn, sync_id, error_message, start_time):
    """Finalize sync_metadata row on failure."""
    duration_ms = int((time.time() - start_time) * 1000)
    conn.execute("""
        UPDATE sync_metadata
        SET completed_at = ?, status = 'failed', error_message = ?, duration_ms = ?
        WHERE sync_id = ?
    """, (datetime.now().isoformat(), str(error_message)[:500], duration_ms, sync_id))
    conn.commit()


# ---------------------------------------------------------------------------
# Differential Helpers
# ---------------------------------------------------------------------------

def get_stored_policy_counts(conn):
    """Get stored pass/fail counts per policy for diff comparison."""
    cursor = conn.execute("""
        SELECT policy_id,
               SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as pass_count,
               SUM(CASE WHEN status='fail' THEN 1 ELSE 0 END) as fail_count
        FROM policy_results
        GROUP BY policy_id
    """)
    return {row['policy_id']: (row['pass_count'], row['fail_count']) for row in cursor.fetchall()}


def get_stored_host_seen_times(conn):
    """Get stored last_seen times for diff comparison on hosts."""
    cursor = conn.execute("SELECT host_id, last_seen FROM fleet_hosts")
    return {row['host_id']: row['last_seen'] for row in cursor.fetchall()}


# ---------------------------------------------------------------------------
# Main Sync Function (Differential)
# ---------------------------------------------------------------------------

def sync_data():
    """
    Main sync function with differential logic.

    Strategy:
    1. Always sync teams, labels (small datasets)
    2. Hosts: upsert all, track which changed via seen_time comparison
    3. Policies: upsert all, compare pass/fail counts to detect changes
    4. Policy Results: only re-fetch for policies where counts changed
    5. Snapshot: create daily compliance snapshot
    """
    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"🔄 Sync started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    init_db()

    if not FLEET_TOKEN:
        print("⚠ FLEET_API_TOKEN not set. Skipping API calls.")
        # Still record metadata so frontend can show status
        conn = get_db_connection()
        sync_id = start_sync_record(conn)
        complete_sync_record(conn, sync_id, 0, 0, 0, start_time)
        conn.close()
        return

    fetch_version()
    conn = get_db_connection()
    sync_id = start_sync_record(conn)
    cursor = conn.cursor()

    try:
        hosts_changed = 0
        policies_changed = 0
        results_changed = 0

        # -- 1. Sync Teams (always full — small dataset) --
        teams = fetch_teams()
        print(f"  📋 Teams: {len(teams)}")
        for team in teams:
            cursor.execute("""
                INSERT OR REPLACE INTO fleet_teams (team_id, team_name, description, created_at)
                VALUES (?, ?, ?, ?)
            """, (team['id'], team['name'], team.get('description'), team.get('created_at')))

        # -- 2. Sync Hosts (differential via seen_time) --
        stored_seen_times = get_stored_host_seen_times(conn)
        hosts = fetch_hosts_paginated()
        print(f"  🖥️  Hosts: {len(hosts)} fetched")

        for host in hosts:
            host_id = host['id']
            new_seen = host.get('seen_time')
            old_seen = stored_seen_times.get(host_id)

            cursor.execute("""
                INSERT OR REPLACE INTO fleet_hosts (
                    host_id, hostname, uuid, platform, platform_version,
                    osquery_version, team_id, team_name, online_status, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                host_id, host['hostname'], host['uuid'], host['platform'],
                host['os_version'], host['osquery_version'], host.get('team_id'),
                host.get('team_name'), host['status'], new_seen
            ))

            if new_seen != old_seen:
                hosts_changed += 1

        print(f"       ↳ {hosts_changed} hosts changed since last sync")

        # -- 3. Sync Labels (always full — small dataset) --
        labels = fetch_labels()
        print(f"  🏷️  Labels: {len(labels)}")
        for label in labels:
            cursor.execute("""
                INSERT OR REPLACE INTO fleet_labels (label_id, label_name, label_type, description)
                VALUES (?, ?, ?, ?)
            """, (label['id'], label['name'], label.get('label_type', 'regular'), label.get('description', '')))

        # -- 4. Sync Host-Label Associations (only for changed hosts) --
        if hosts_changed > 0:
            changed_host_ids = [
                h['id'] for h in hosts
                if h.get('seen_time') != stored_seen_times.get(h['id'])
            ]
            print(f"  🔗 Syncing labels for {len(changed_host_ids)} changed hosts...")

            # Remove old labels for changed hosts only
            if changed_host_ids:
                placeholders = ','.join('?' * len(changed_host_ids))
                cursor.execute(f"DELETE FROM host_labels WHERE host_id IN ({placeholders})", changed_host_ids)

            def get_host_labels(host_id):
                details = fetch_host_details(host_id)
                if details and 'labels' in details:
                    return [(host_id, label['id']) for label in details['labels']]
                return []

            label_count = 0
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(get_host_labels, hid): hid for hid in changed_host_ids}
                for future in as_completed(futures):
                    host_labels = future.result()
                    if host_labels:
                        cursor.executemany(
                            "INSERT OR IGNORE INTO host_labels (host_id, label_id) VALUES (?, ?)",
                            host_labels
                        )
                        label_count += len(host_labels)
            print(f"       ↳ {label_count} host-label associations updated")
        else:
            print(f"  🔗 Host labels: skipped (no host changes)")

        # -- 5. Sync Policies (always full — small dataset) --
        policies = fetch_policies(teams)
        print(f"  📜 Policies: {len(policies)}")

        for policy in policies:
            policy_name = policy['name']
            description = policy.get('description') or ""

            match = CIS_REGEX.search(policy_name)
            if not match:
                match = CIS_FALLBACK_REGEX.search(policy_name)
            if not match:
                match = CIS_REGEX.search(description)
            cis_control = match.group(1) if match else None

            cursor.execute("""
                INSERT OR REPLACE INTO cis_policies (
                    policy_id, policy_name, cis_control, description, resolution, query, category, severity, platform
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                policy['id'], policy_name, cis_control,
                policy.get('description'), policy.get('resolution'), policy.get('query'),
                'General', 'Medium', policy.get('platform', 'all')
            ))

        # -- 6. Differential Policy Results (counts-first) --
        stored_counts = get_stored_policy_counts(conn)
        changed_policies = []

        for policy in policies:
            pid = policy['id']
            api_pass = policy.get('passing_host_count', 0) or 0
            api_fail = policy.get('failing_host_count', 0) or 0

            stored = stored_counts.get(pid, (0, 0))
            stored_pass, stored_fail = stored

            if api_pass != stored_pass or api_fail != stored_fail:
                changed_policies.append(policy)

        print(f"  📊 Policy results: {len(changed_policies)}/{len(policies)} policies have count changes")

        if changed_policies:
            # Remove old results for changed policies only
            changed_pids = [p['id'] for p in changed_policies]
            placeholders = ','.join('?' * len(changed_pids))
            cursor.execute(f"DELETE FROM policy_results WHERE policy_id IN ({placeholders})", changed_pids)

            # Fetch new results in parallel
            tasks = []
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                for policy in changed_policies:
                    pid = policy['id']
                    pass_count = policy.get('passing_host_count', 0) or 0
                    fail_count = policy.get('failing_host_count', 0) or 0

                    if pass_count > 0:
                        tasks.append(executor.submit(fetch_policy_hosts, pid, "pass"))
                    if fail_count > 0:
                        tasks.append(executor.submit(fetch_policy_hosts, pid, "fail"))

                print(f"       ↳ Processing {len(tasks)} API requests...")

                for future in as_completed(tasks):
                    results = future.result()
                    if results:
                        cursor.executemany("""
                            INSERT OR REPLACE INTO policy_results (policy_id, host_id, status, checked_at)
                            VALUES (?, ?, ?, ?)
                        """, results)
                        results_changed += len(results)

            policies_changed = len(changed_policies)
            print(f"       ↳ {results_changed} results upserted for {policies_changed} policies")
        else:
            print(f"       ↳ No count changes — results skipped ✨")

        # -- 7. Daily Compliance Snapshot --
        create_compliance_snapshot(conn)

        # -- 8. Finalize --
        conn.commit()
        complete_sync_record(conn, sync_id, hosts_changed, policies_changed, results_changed, start_time)

        elapsed = time.time() - start_time
        print(f"\n✅ Sync completed in {elapsed:.1f}s")
        print(f"   Hosts Δ={hosts_changed}, Policies Δ={policies_changed}, Results Δ={results_changed}")

    except Exception as e:
        print(f"\n❌ Sync failed: {e}")
        fail_sync_record(conn, sync_id, e, start_time)
        conn.rollback()
    finally:
        conn.close()


def create_compliance_snapshot(conn):
    """Create a daily compliance snapshot for trends."""
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')

    cursor.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passing
        FROM policy_results
    """)
    row = cursor.fetchone()
    total = row['total'] or 0
    passing = row['passing'] or 0
    global_score = (passing / total * 100) if total > 0 else 0

    cursor.execute("""
        INSERT OR REPLACE INTO compliance_snapshots (snapshot_date, team_id, compliance_score, passing_hosts)
        VALUES (?, NULL, ?, ?)
    """, (today, global_score, passing))

    cursor.execute("""
        SELECT h.team_id,
               COUNT(*) as total,
               SUM(CASE WHEN pr.status='pass' THEN 1 ELSE 0 END) as passing
        FROM policy_results pr
        JOIN fleet_hosts h ON pr.host_id = h.host_id
        WHERE h.team_id IS NOT NULL
        GROUP BY h.team_id
    """)
    for tr in cursor.fetchall():
        t_total = tr['total']
        t_passing = tr['passing']
        t_score = (t_passing / t_total * 100) if t_total > 0 else 0
        cursor.execute("""
            INSERT OR REPLACE INTO compliance_snapshots (snapshot_date, team_id, compliance_score, passing_hosts)
            VALUES (?, ?, ?, ?)
        """, (today, tr['team_id'], t_score, t_passing))

    print(f"  📸 Snapshot: {today} (Global: {global_score:.1f}%)")


if __name__ == "__main__":
    sync_data()
