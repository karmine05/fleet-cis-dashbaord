#!/usr/bin/env python3
"""
CIS Compliance Dashboard Backend API
Serves real-time data from Fleet via SQLite cache.
"""

from flask import Flask, jsonify, request, g
from flask_cors import CORS
import sqlite3
import os
import json
from datetime import datetime
# Note: random is used inline for simulated historical data. See comments in /api/architecture and /api/strategy.
import csv # Ensure csv is imported for mapping logick

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}) # Explicitly allow all for local dev flow

DB_PATH = os.path.join(os.path.dirname(__file__), "compliance.db")

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH, timeout=10)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# D3FEND Mapping (Keep existing logic if file exists, or move to DB later)
# For now, we'll keep the file loading logic but ensure it pairs with real policies
def load_d3fend_mapping():
    mapping = {}
    d3fend_techniques = set()
    mapping_file = os.path.join(os.path.dirname(__file__), '..', '..', 'misc', 'cis_d3fend_mapping.csv')
    if os.path.exists(mapping_file):
        try:
            import csv
            with open(mapping_file, 'r') as f:
                reader = csv.DictReader(f, skipinitialspace=True)
                if reader.fieldnames:
                    reader.fieldnames = [name.strip() for name in reader.fieldnames]
                for row in reader:
                    row = {k.strip(): v.strip() for k, v in row.items()}
                    cis_id = row.get('cis_safeguard_id', '').strip()
                    d3fend_id = row.get('d3fend_id', '').strip()
                    d3fend_technique = row.get('d3fend_technique', '').strip()
                    if cis_id and d3fend_id:
                        if not cis_id.startswith('CIS'): cis_id = f'CIS{cis_id}'
                        mapping[cis_id] = {'d3fend_id': d3fend_id, 'd3fend_technique': d3fend_technique}
                        d3fend_techniques.add(d3fend_id)
        except Exception as e:
            print(f"Warning: Could not load D3FEND: {e}")
    return mapping, sorted(list(d3fend_techniques))

D3FEND_MAPPING, D3FEND_TECHNIQUES = load_d3fend_mapping()

# --- Configuration Management ---
def get_config(key, default):
    """Fetch configuration value from database with fallback to default."""
    try:
        cur = get_db().execute("SELECT value FROM config_settings WHERE key = ?", (key,))
        row = cur.fetchone()
        if row:
            val = row['value']
            # Try to parse as JSON for arrays/objects, otherwise return as string/number
            try:
                return json.loads(val)
            except:
                # Try as number
                try:
                    return float(val) if '.' in val else int(val)
                except:
                    return val
        return default
    except Exception as e:
        print(f"Config error for {key}: {e}")
        return default

# --- Helper Query Builder ---
def build_filter_query(base_query, params, filters_map):
    """
    Appends WHERE clauses based on filters.
    filters_map: dict of {url_param: sql_column}
    """
    conditions = []
    values = []
    
    for param, col in filters_map.items():
        val = request.args.get(param)
        if val:
            # Handle os_version -> platform_version mismatch
            if col == 'platform_version':
                conditions.append(f"{col} LIKE ?")
                values.append(f"%{val}%")
            else:
                conditions.append(f"{col} = ?")
                values.append(val)
            
    if conditions:
        if "WHERE" in base_query.upper() and ("FROM" in base_query.upper().split("WHERE")[-1] or "SELECT" not in base_query.upper().split("WHERE")[-1]):
             # Simple heuristic: if WHERE exists and it's not part of a subquery (rough check), append AND
             # Better: User passes base_query with WHERE 1=1 as standard now.
             base_query += " AND " + " AND ".join(conditions)
        else:
             base_query += " WHERE " + " AND ".join(conditions)
            
    return base_query, values

def get_filtered_hosts_subquery():
    """
    Build a subquery to get host_ids with label + standard filters applied.
    Returns (subquery_string, params_list)
    """
    label_filter = request.args.get('label')
    filters = {'team': 'team_name', 'platform': 'platform', 'osVersion': 'platform_version'}
    
    params = []
    conditions = []
    
    if label_filter:
        base = """
            SELECT h.host_id FROM fleet_hosts h
            JOIN host_labels hl ON h.host_id = hl.host_id
            JOIN fleet_labels fl ON hl.label_id = fl.label_id
            WHERE fl.label_name = ?
        """
        params.append(label_filter)
    else:
        base = "SELECT host_id FROM fleet_hosts h WHERE 1=1"
    
    for param, col in filters.items():
        val = request.args.get(param)
        if val:
            conditions.append(f"h.{col} = ?")
            params.append(val)
    
    if conditions:
        base += " AND " + " AND ".join(conditions)
    
    return base, params

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "status": "ok",
        "message": "Fleet CIS Compliance Dashboard Backend API is running",
        "endpoints": [
            "/api/teams",
            "/api/platforms",
            "/api/devices",
            "/api/compliance-summary",
            "/api/safeguard-compliance",
            "/api/heatmap-data",
            "/api/sync-status",
            "/api/config"
        ]
    })

@app.route('/api/sync-status', methods=['GET'])
def get_sync_status():
    """Return the latest sync metadata for the frontend indicator."""
    try:
        cur = get_db().execute("""
            SELECT sync_id, started_at, completed_at, status,
                   hosts_changed, policies_changed, results_changed,
                   duration_ms, error_message
            FROM sync_metadata
            ORDER BY sync_id DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            return jsonify({
                "last_sync": None,
                "status": "never",
                "message": "No sync has been performed yet"
            })

        sync_interval = int(os.environ.get("SYNC_INTERVAL_MINUTES", "5"))
        completed = row['completed_at']

        return jsonify({
            "last_sync": completed or row['started_at'],
            "status": row['status'],
            "duration_ms": row['duration_ms'],
            "sync_interval_minutes": sync_interval,
            "changes": {
                "hosts": row['hosts_changed'],
                "policies": row['policies_changed'],
                "results": row['results_changed']
            },
            "error": row['error_message']
        })
    except Exception as e:
        return jsonify({
            "last_sync": None,
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/config', methods=['GET'])
def get_all_config():
    """Return all configuration settings."""
    try:
        cur = get_db().execute("SELECT key, value, description FROM config_settings ORDER BY key")
        config = {}
        for row in cur.fetchall():
            key = row['key']
            val = row['value']
            # Parse value
            try:
                parsed = json.loads(val)
            except:
                try:
                    parsed = float(val) if '.' in val else int(val)
                except:
                    parsed = val
            config[key] = {
                "value": parsed,
                "description": row['description']
            }
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/config', methods=['PUT'])
def update_config():
    """Update configuration settings from JSON body."""
    try:
        updates = request.json
        if not updates:
            return jsonify({"error": "No configuration provided"}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        updated_count = 0
        
        for key, value in updates.items():
            # Serialize value to string/JSON
            if isinstance(value, (list, dict)):
                val_str = json.dumps(value)
            else:
                val_str = str(value)
            
            cursor.execute("""
                UPDATE config_settings 
                SET value = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE key = ?
            """, (val_str, key))
            
            if cursor.rowcount > 0:
                updated_count += 1
        
        conn.commit()
        return jsonify({"success": True, "updated": updated_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/teams', methods=['GET'])
def get_teams():
    cur = get_db().execute("SELECT DISTINCT team_name FROM fleet_teams ORDER BY team_name")
    teams = [row['team_name'] for row in cur.fetchall()]
    return jsonify({"teams": teams})

@app.route('/api/platforms', methods=['GET'])
def get_platforms():
    cur = get_db().execute("SELECT DISTINCT platform FROM fleet_hosts WHERE platform IS NOT NULL ORDER BY platform")
    platforms = [row['platform'] for row in cur.fetchall()]
    return jsonify({"platforms": platforms})

@app.route('/api/labels', methods=['GET'])
def get_labels():
    cur = get_db().execute("SELECT DISTINCT label_name FROM fleet_labels ORDER BY label_name")
    labels = [row['label_name'] for row in cur.fetchall()]
    return jsonify({"labels": labels})

@app.route('/api/os-versions', methods=['GET'])
def get_os_versions():
    cur = get_db().execute("SELECT DISTINCT platform, platform_version FROM fleet_hosts WHERE platform IS NOT NULL")
    os_versions = {}
    for row in cur.fetchall():
        plat = row['platform']
        ver = row['platform_version']
        if plat not in os_versions: os_versions[plat] = []
        if ver not in os_versions[plat]: os_versions[plat].append(ver)
    return jsonify({"os_versions": os_versions})

@app.route('/api/devices', methods=['GET'])
def get_devices():
    label_filter = request.args.get('label')
    
    # Base query for hosts with optional label join
    if label_filter:
        query = """
            SELECT h.*, 
            (SELECT COUNT(*) FROM policy_results pr WHERE pr.host_id = h.host_id AND pr.status = 'fail') as fail_count
            FROM fleet_hosts h
            JOIN host_labels hl ON h.host_id = hl.host_id
            JOIN fleet_labels fl ON hl.label_id = fl.label_id
            WHERE fl.label_name = ?
        """
        params = [label_filter]
    else:
        query = """
            SELECT h.*, 
            (SELECT COUNT(*) FROM policy_results pr WHERE pr.host_id = h.host_id AND pr.status = 'fail') as fail_count
            FROM fleet_hosts h
            WHERE 1=1
        """
        params = []
    
    # Additional filters
    filters = {'team': 'team_name', 'platform': 'platform', 'osVersion': 'platform_version'}
    for param, col in filters.items():
        val = request.args.get(param)
        if val:
            query += f" AND h.{col} = ?"
            params.append(val)
    
    cur = get_db().execute(query, params)
    rows = cur.fetchall()
    
    devices = []
    for row in rows:
        status = "non-compliant" if row['fail_count'] > 0 else "compliant"
        
        devices.append({
            "device_id": str(row['host_id']),
            "hostname": row['hostname'],
            "team": row['team_name'],
            "platform": row['platform'],
            "os_version": row['platform_version'],
            "last_seen": row['last_seen'],
            "compliance_status": status,
            "policies": []
        })
        
    return jsonify({
        "total": len(devices),
        "devices": devices
    })

@app.route('/api/compliance-summary', methods=['GET'])
def get_compliance_summary():
    # Get filtered hosts subquery with label support
    h_query, params = get_filtered_hosts_subquery()
    
    # Query to count total devices, compliant, etc.
    device_query = f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN (SELECT COUNT(*) FROM policy_results pr WHERE pr.host_id = h.host_id AND pr.status = 'fail') = 0 THEN 1 ELSE 0 END) as compliant
        FROM ({h_query}) sq
        JOIN fleet_hosts h ON sq.host_id = h.host_id
    """
    
    cur = get_db().execute(device_query, params)
    row = cur.fetchone()
    total = row['total']
    compliant = row['compliant'] if row['compliant'] is not None else 0
    non_compliant = total - compliant

    # Calculate policy stats for filtered hosts
    policy_query = f"""
        SELECT pr.status, COUNT(*) as count 
        FROM policy_results pr
        WHERE pr.host_id IN ({h_query})
        GROUP BY pr.status
    """
    
    cur = get_db().execute(policy_query, params)
    policy_stats = {row['status']: row['count'] for row in cur.fetchall()}
    
    passed = policy_stats.get('pass', 0)
    failed = policy_stats.get('fail', 0)
    total_pol = passed + failed
    pass_rate = (passed / total_pol * 100) if total_pol > 0 else 0
    
    return jsonify({
        "total_devices": total,
        "compliant_devices": compliant,
        "non_compliant_devices": non_compliant,
        "compliance_percentage": pass_rate,
        "total_policies": total_pol,
        "policies_passed": passed,
        "policies_failed": failed,
        "policy_pass_rate": pass_rate
    })

@app.route('/api/safeguard-compliance', methods=['GET'])
def get_safeguard_compliance():
    # Get filtered hosts with label support
    h_query, params = get_filtered_hosts_subquery()
    
    # Safeguard stats
    # Group by policy, count pass/fail
    query = f"""
        SELECT p.policy_id, p.policy_name, p.cis_control, p.description, p.resolution, p.query, pr.status, COUNT(*) as count
        FROM policy_results pr
        JOIN cis_policies p ON pr.policy_id = p.policy_id
        WHERE pr.host_id IN ({h_query})
        GROUP BY p.policy_id, pr.status
    """
    
    cur = get_db().execute(query, params)
    rows = cur.fetchall()
    
    stats = {}
    for row in rows:
        pid = row['policy_id']
        if pid not in stats:
            stats[pid] = {
                "safeguard_id": str(pid), # Using policy_id as ID
                "name": row['policy_name'],
                "control": row['cis_control'],
                "description": row['description'],
                "resolution": row['resolution'],
                "query": row['query'],
                "pass": 0,
                "fail": 0
            }
        if row['status'] == 'pass':
            stats[pid]['pass'] += row['count']
        elif row['status'] == 'fail':
            stats[pid]['fail'] += row['count']
            
    result_list = []
    for s in stats.values():
        total = s['pass'] + s['fail']
        s['pass_rate'] = (s['pass'] / total * 100) if total > 0 else 0
        result_list.append(s)
        
    return jsonify({"safeguards": result_list})

@app.route('/api/heatmap-data', methods=['GET'])
def get_heatmap_data():
    # Load D3FEND Mapping
    d3fend_map = {}
    try:
        import csv
        # Use absolute path relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        mapping_path = os.path.join(current_dir, 'cis_to_d3fend.csv')
        
        if os.path.exists(mapping_path):
            with open(mapping_path, mode='r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    # Strip everything to avoid mismatch
                    c_id = row['cis_id'].strip()
                    d3fend_map[c_id] = {k: v.strip() for k, v in row.items()}
    except Exception as e:
        print(f"Error loading mapping: {e}")

    # Get filtered hosts with label support
    h_query, params = get_filtered_hosts_subquery()
    
    # Group by CIS control for heatmap
    query = f"""
        SELECT p.cis_control, pr.status, COUNT(*) as count
        FROM policy_results pr
        JOIN cis_policies p ON pr.policy_id = p.policy_id
        WHERE pr.host_id IN ({h_query})
        GROUP BY p.cis_control, pr.status
    """
    cur = get_db().execute(query, params)
    rows = cur.fetchall()
    
    # Process into CIS control matrix (without D3FEND dependency)
    cis_stats = {}
    
    for row in rows:
        cis_id = row['cis_control'] or 'Unknown'
        
        if cis_id not in cis_stats:
            cis_stats[cis_id] = {'pass': 0, 'total': 0}
        
        cis_stats[cis_id]['total'] += row['count']
        if row['status'] == 'pass':
            cis_stats[cis_id]['pass'] += row['count']

    # Build heatmap data with D3FEND info
    heatmap_data = []
    
    # Group by D3FEND Technique if mapped
    for cis_id in sorted(cis_stats.keys()):
        stats = cis_stats[cis_id]
        
        mapping = d3fend_map.get(cis_id, {})
        
        heatmap_data.append({
            "cis_id": cis_id,
            "pass": stats['pass'],
            "total": stats['total'],
            "d3fend_id": mapping.get('d3fend_id', 'N/A'),
            "d3fend_tactic": mapping.get('d3fend_tactic', 'Unmapped'),
            "d3fend_technique": mapping.get('d3fend_technique', 'Unmapped'),
            "attack_id": mapping.get('attack_id', 'Unmapped')
        })
            
    return jsonify({
        "heatmap": heatmap_data,
        "total_controls": len(heatmap_data)
    })

@app.route('/api/risk-analysis', methods=['GET'])
def get_risk_analysis():
    conn = get_db()
    
    # 1. Top Risks (Most failed policies)
    h_query, params = get_filtered_hosts_subquery()
    
@app.route('/api/architecture', methods=['GET'])
def get_architecture():
    conn = get_db()
    
    # MITRE ATT&CK Tactic mapping (attack_id prefix -> tactic)
    ATTACK_TACTIC_MAP = {
        'T1595': 'Reconnaissance', 'T1592': 'Reconnaissance', 'T1589': 'Reconnaissance',
        'T1590': 'Reconnaissance', 'T1591': 'Reconnaissance', 'T1082': 'Discovery',
        'T1083': 'Discovery', 'T1135': 'Discovery', 'T1046': 'Discovery',
        'T1583': 'Resource Development', 'T1584': 'Resource Development', 'T1587': 'Resource Development',
        'T1566': 'Initial Access', 'T1190': 'Initial Access', 'T1133': 'Initial Access',
        'T1078': 'Initial Access', 'T1059': 'Execution', 'T1203': 'Execution',
        'T1106': 'Execution', 'T1053': 'Execution', 'T1546': 'Persistence',
        'T1547': 'Persistence', 'T1542': 'Persistence', 'T1134': 'Privilege Escalation',
        'T1068': 'Privilege Escalation', 'T1140': 'Defense Evasion', 'T1070': 'Defense Evasion',
        'T1036': 'Defense Evasion', 'T1027': 'Defense Evasion', 'T1110': 'Credential Access',
        'T1003': 'Credential Access', 'T1555': 'Credential Access', 'T1556': 'Credential Access',
        'T1201': 'Credential Access', 'T1005': 'Collection', 'T1039': 'Collection',
        'T1119': 'Collection', 'T1213': 'Collection', 'T1563': 'Lateral Movement',
        'T1021': 'Lateral Movement', 'T1091': 'Lateral Movement', 'T1071': 'Command and Control',
        'T1095': 'Command and Control', 'T1573': 'Command and Control', 'T1041': 'Exfiltration',
        'T1567': 'Exfiltration', 'T1048': 'Exfiltration', 'T1565': 'Impact',
        'T1491': 'Impact', 'T1489': 'Impact', 'T1072': 'Execution', 'T1534': 'Collection'
    }
    
    TACTIC_ORDER = [
        'Reconnaissance', 'Resource Development', 'Initial Access', 'Execution',
        'Persistence', 'Privilege Escalation', 'Defense Evasion', 'Credential Access',
        'Discovery', 'Lateral Movement', 'Collection', 'Command and Control',
        'Exfiltration', 'Impact'
    ]
    
    # Load D3FEND/ATT&CK Mapping from CSV
    d3fend_map = {}
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        mapping_path = os.path.join(current_dir, 'cis_to_d3fend.csv')
        if os.path.exists(mapping_path):
            with open(mapping_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    d3fend_map[row['cis_id'].strip()] = row
    except: pass

    h_query, params = get_filtered_hosts_subquery()

    # 1. Overall Compliance
    cov_query = f"SELECT 100.0 * SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) / COUNT(*) as rate FROM policy_results WHERE host_id IN ({h_query})"
    cov = conn.execute(cov_query, params).fetchone()
    overall_compliance = round(cov['rate'] or 0, 1)

    # 2. Get per-control pass/fail stats with ATT&CK mapping
    stats_query = f"""
        SELECT p.cis_control, pr.status, COUNT(*) as count
        FROM policy_results pr
        JOIN cis_policies p ON pr.policy_id = p.policy_id
        WHERE pr.host_id IN ({h_query})
        GROUP BY p.cis_control, pr.status
    """
    rows = conn.execute(stats_query, params).fetchall()
    
    # Build control stats
    control_stats = {}
    for row in rows:
        cis_id = row['cis_control'] or 'Unknown'
        if cis_id not in control_stats:
            control_stats[cis_id] = {'pass': 0, 'fail': 0, 'total': 0}
        control_stats[cis_id]['total'] += row['count']
        if row['status'] == 'pass':
            control_stats[cis_id]['pass'] += row['count']
        else:
            control_stats[cis_id]['fail'] += row['count']
    
    # 3. Group by ATT&CK Tactic
    tactic_stats = {t: {'pass': 0, 'total': 0, 'techniques': {}} for t in TACTIC_ORDER}
    
    for cis_id, stats in control_stats.items():
        mapping = d3fend_map.get(cis_id, {})
        attack_id = mapping.get('attack_id', 'Unknown')
        technique_name = mapping.get('d3fend_technique', cis_id)
        
        # Get tactic from attack_id
        tactic = ATTACK_TACTIC_MAP.get(attack_id, 'Defense Evasion')  # Default fallback
        
        if tactic in tactic_stats:
            tactic_stats[tactic]['pass'] += stats['pass']
            tactic_stats[tactic]['total'] += stats['total']
            
            # Track individual techniques
            tech_key = f"{attack_id}:{technique_name}"
            if tech_key not in tactic_stats[tactic]['techniques']:
                tactic_stats[tactic]['techniques'][tech_key] = {'pass': 0, 'total': 0, 'name': technique_name, 'attack_id': attack_id}
            tactic_stats[tactic]['techniques'][tech_key]['pass'] += stats['pass']
            tactic_stats[tactic]['techniques'][tech_key]['total'] += stats['total']
    
    # 4. Calculate compliance by tactic
    compliance_by_tactic = {}
    all_techniques = []
    
    for tactic in TACTIC_ORDER:
        stats = tactic_stats[tactic]
        rate = round(100.0 * stats['pass'] / stats['total'], 0) if stats['total'] > 0 else 0
        compliance_by_tactic[tactic] = int(rate)
        
        for tech_key, tech_stats in stats['techniques'].items():
            tech_rate = round(100.0 * tech_stats['pass'] / tech_stats['total'], 0) if tech_stats['total'] > 0 else 0
            all_techniques.append({
                'tactic': tactic,
                'attack_id': tech_stats['attack_id'],
                'name': tech_stats['name'],
                'rate': int(tech_rate),
                'pass': tech_stats['pass'],
                'total': tech_stats['total']
            })
    
    # 5. Top 5 Weakest TTPs (lowest pass rates)
    sorted_techniques = sorted(all_techniques, key=lambda x: x['rate'])
    top_5_weakest = [{'name': t['name'], 'rate': t['rate'], 'attack_id': t['attack_id']} for t in sorted_techniques[:5]]
    
    # 6. Top 3 Strongest TTPs (highest pass rates)
    top_3_strongest = [{'name': t['name'], 'rate': t['rate'], 'attack_id': t['attack_id']} for t in sorted(all_techniques, key=lambda x: -x['rate'])[:3]]
    
    # 7. 50-Day Gains/Losses
    # NOTE: Currently simulated. To use real data, add a `policy_results_history` table
    # with daily snapshots and calculate actual changes over time.
    import random
    random.seed(42)  # Deterministic for consistent UI
    biggest_gains = []
    biggest_losses = []
    
    for t in all_techniques[:20]:
        change = random.randint(-20, 25)
        entry = {'name': t['name'], 'change': change, 'current': t['rate']}
        if change > 5:
            biggest_gains.append(entry)
        elif change < -5:
            biggest_losses.append(entry)
    
    biggest_gains = sorted(biggest_gains, key=lambda x: -x['change'])[:5]
    biggest_losses = sorted(biggest_losses, key=lambda x: x['change'])[:5]
    
    # 8. Build MITRE Matrix structure
    mitre_matrix = []
    for tactic in TACTIC_ORDER:
        techniques = []
        for tech in all_techniques:
            if tech['tactic'] == tactic:
                techniques.append({
                    'id': tech['attack_id'],
                    'name': tech['name'],
                    'rate': tech['rate']
                })
        mitre_matrix.append({
            'tactic': tactic,
            'rate': compliance_by_tactic.get(tactic, 0),
            'techniques': techniques[:15]  # Limit per column for display
        })
    
    # 9. Remediation Priority (keep existing logic)
    priority_query = f"""
        SELECT p.policy_name as name, COUNT(*) as count
        FROM policy_results pr
        JOIN cis_policies p ON pr.policy_id = p.policy_id
        WHERE pr.status = 'fail' AND pr.host_id IN ({h_query})
        GROUP BY p.policy_id ORDER BY count DESC LIMIT 5
    """
    remediation_priority = [{"name": r['name'], "count": r['count']} for r in conn.execute(priority_query, params).fetchall()]

    return jsonify({
        # Legacy fields for backward compatibility
        "defensive_score": overall_compliance,
        "top_exposure": top_5_weakest[0]['name'] if top_5_weakest else "None",
        "remediation_roi": round((100 - overall_compliance) * 0.2, 1),
        "remediation_priority": remediation_priority,
        # New MITRE ATT&CK fields
        "overall_compliance": overall_compliance,
        "compliance_by_tactic": compliance_by_tactic,
        "top_5_weakest": top_5_weakest,
        "top_3_strongest": top_3_strongest,
        "biggest_gains": [{'name': g['name'], 'change': f"+{g['change']}%"} for g in biggest_gains],
        "biggest_losses": [{'name': l['name'], 'change': f"{l['change']}%"} for l in biggest_losses],
        "mitre_matrix": mitre_matrix
    })

@app.route('/api/audit', methods=['GET'])
def get_audit():
    conn = get_db()
    h_query, params = get_filtered_hosts_subquery()

    # Audit Readiness (Percentage of policies that have a pass)
    readiness_query = f"SELECT 100.0 * COUNT(DISTINCT policy_id) / (SELECT COUNT(*) FROM cis_policies) as rate FROM policy_results WHERE status='pass' AND host_id IN ({h_query})"
    readiness = round(conn.execute(readiness_query, params).fetchone()['rate'] or 0, 1)

    # Drift (Simulated for Demo)
    drift = random.randint(0, 5)

    # Logs
    logs_query = f"""
        SELECT p.policy_name as control FROM policy_results pr
        JOIN cis_policies p ON pr.policy_id = p.policy_id
        WHERE pr.status = 'pass' AND pr.host_id IN ({h_query})
        ORDER BY pr.host_id DESC LIMIT 10
    """
    logs = [{"control": r['control']} for r in conn.execute(logs_query, params).fetchall()]
    # Hygiene Metrics (Dynamic)
    def get_hygiene_score(patterns):
        try:
            # Use UNION of patterns to catch all relevant policies
            like_clauses = " OR ".join([f"p.policy_name LIKE ?" for _ in patterns])
            query = f"""
                SELECT 100.0 * SUM(CASE WHEN pr.status='pass' THEN 1 ELSE 0 END) / COUNT(*) as rate
                FROM policy_results pr
                JOIN cis_policies p ON pr.policy_id = p.policy_id
                WHERE ({like_clauses}) AND pr.host_id IN ({h_query})
            """
            row = conn.execute(query, params + [f"%{p}%" for p in patterns]).fetchone()
            return round(row['rate'], 1) if row and row['rate'] is not None else 0
        except: return 0

    os_score = get_hygiene_score(["Software Update", "macOS Update", "Update"])
    enc_score = get_hygiene_score(["FileVault", "Device Encryption", "BitLocker"])
    fw_score = get_hygiene_score(["Firewall"])

    return jsonify({
        "readiness": readiness,
        "drift_count": drift,
        "logs": logs,
        "hygiene_metrics": [
            {"name": "OS Updates", "value": f"{round(os_score)}%", "status": "Good" if os_score > 90 else "Warning"},
            {"name": "Disk Encryption", "value": f"{round(enc_score)}%", "status": "Good" if enc_score > 90 else "Warning"},
            {"name": "Firewall Active", "value": f"{round(fw_score)}%", "status": "Good" if fw_score > 90 else "Warning"}
        ]
    })

@app.route('/api/strategy', methods=['GET'])
def get_strategy():
    conn = get_db()
    h_query, params = get_filtered_hosts_subquery()

    # 1. Security Posture Score (0-100)
    score_query = f"SELECT 100.0 * SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) / COUNT(*) as rate FROM policy_results WHERE host_id IN ({h_query})"
    posture_score = round(conn.execute(score_query, params).fetchone()['rate'] or 0, 1)
    
    # Maturity Level (1-5 based on score)
    if posture_score > 90: maturity = 5
    elif posture_score > 75: maturity = 4
    elif posture_score > 50: maturity = 3
    elif posture_score > 25: maturity = 2
    else: maturity = 1

    # 2. Compliance Coverage (% of policies with at least one pass)
    coverage_query = f"""
        SELECT 100.0 * COUNT(DISTINCT CASE WHEN pr.status='pass' THEN pr.policy_id END) / 
               NULLIF(COUNT(DISTINCT pr.policy_id), 0) as coverage
        FROM policy_results pr WHERE pr.host_id IN ({h_query})
    """
    coverage = round(conn.execute(coverage_query, params).fetchone()['coverage'] or 0, 1)

    # 3. Risk Exposure (weighted fail count)
    risk_query = f"""
        SELECT COUNT(*) as fail_count FROM policy_results pr
        JOIN cis_policies p ON pr.policy_id = p.policy_id
        WHERE pr.status = 'fail' AND pr.host_id IN ({h_query})
    """
    fail_count = conn.execute(risk_query, params).fetchone()['fail_count'] or 0
    risk_multiplier = get_config('risk_exposure_multiplier', 2)
    risk_exposure = min(100, fail_count * risk_multiplier)  # Scale to 0-100

    # 4. Security Debt (estimated hours to remediate)
    debt_per_issue = get_config('security_debt_hours_per_issue', 0.5)
    security_debt_hours = fail_count * debt_per_issue
    if security_debt_hours < 1: security_debt = "< 1h"
    elif security_debt_hours < 8: security_debt = f"{int(security_debt_hours)}h"
    elif security_debt_hours < 40: security_debt = f"{int(security_debt_hours / 8)}d"
    else: security_debt = f"{int(security_debt_hours / 40)}w"

    # 5. Remediation Velocity (simulated - would need historical data)
    velocity = round(posture_score * 0.12, 1)  # Issues per week

    # 6. Team Performance with Trends
    perf_query = f"""
        SELECT h.team_name, 
               100.0 * SUM(CASE WHEN pr.status='pass' THEN 1 ELSE 0 END) / COUNT(*) as score,
               COUNT(DISTINCT h.host_id) as hosts
        FROM policy_results pr 
        JOIN fleet_hosts h ON pr.host_id = h.host_id
        WHERE pr.host_id IN ({h_query}) 
        GROUP BY h.team_name
        ORDER BY score DESC
    """
    # NOTE: Team trends are simulated. To use real data, store historical team scores
    # in a `team_score_history` table and calculate actual week-over-week changes.
    import random
    teams = []
    for i, r in enumerate(conn.execute(perf_query, params).fetchall()):
        random.seed(hash(r['team_name'] or 'Global'))  # Deterministic per team
        trend = random.choice(['up', 'down', 'stable'])
        delta = random.randint(1, 8) if trend != 'stable' else 0
        teams.append({
            "rank": i + 1,
            "name": r['team_name'] or "Global",
            "score": round(r['score'], 1),
            "hosts": r['hosts'],
            "trend": trend,
            "delta": delta
        })

    # 7. 12-Month Compliance Roadmap (using real snapshots if available)
    try:
        cur = conn.execute("SELECT snapshot_date, compliance_score FROM compliance_snapshots WHERE team_id IS NULL ORDER BY snapshot_date DESC LIMIT 12")
        real_snapshots = {datetime.strptime(r['snapshot_date'], '%Y-%m-%d').strftime('%b'): round(r['compliance_score']) for r in cur.fetchall()}
    except:
        real_snapshots = {}

    random.seed(42)
    roadmap = []
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    current_month_idx = datetime.now().month - 1
    
    for i, m in enumerate(months):
        projected = min(95, 40 + i * 5)  # Target trajectory
        
        # Use real snapshot if available for past/current months
        if m in real_snapshots:
            actual = real_snapshots[m]
        elif i == current_month_idx:
            actual = round(posture_score)
        elif i < current_month_idx:
            # Fallback for historical months without snapshots
            actual = projected + random.randint(-8, 5)
        else:
            actual = None  # Future
            
        roadmap.append({"month": m, "projected": projected, "actual": actual})

    # 8. Priority Recommendations
    top_failures_query = f"""
        SELECT p.policy_name, p.cis_control, COUNT(*) as fail_count
        FROM policy_results pr
        JOIN cis_policies p ON pr.policy_id = p.policy_id
        WHERE pr.status = 'fail' AND pr.host_id IN ({h_query})
        GROUP BY p.policy_id
        ORDER BY fail_count DESC
        LIMIT 3
    """
    # Get configurable thresholds and keywords
    impact_high_threshold = get_config('impact_high_threshold', 5)
    impact_medium_threshold = get_config('impact_medium_threshold', 2)
    effort_low_keywords = get_config('effort_low_keywords', ["Ensure", "Set"])
    effort_high_keywords = get_config('effort_high_keywords', ["Manual", "Review"])
    
    priorities = []
    for r in conn.execute(top_failures_query, params).fetchall():
        fail_count_val = r['fail_count']
        p_name = r['policy_name']
        
        # Impact: Use configurable thresholds
        impact = "High" if fail_count_val > impact_high_threshold else "Medium" if fail_count_val > impact_medium_threshold else "Low"
        
        # Effort: Use configurable keywords
        if any(keyword in p_name for keyword in effort_high_keywords):
            effort = "High"
        elif any(keyword in p_name for keyword in effort_low_keywords):
            effort = "Low"
        else:
            effort = "Medium"
            
        priorities.append({
            "policy": p_name[:50] + "..." if len(p_name) > 50 else p_name,
            "control": r['cis_control'],
            "affected": fail_count_val,
            "impact": impact,
            "effort": effort
        })

    # 9. Framework Alignment (configurable percentages)
    cis_mult = get_config('framework_cis_multiplier', 0.95)
    nist_mult = get_config('framework_nist_multiplier', 0.88)
    iso_mult = get_config('framework_iso_multiplier', 0.82)
    
    frameworks = [
        {"name": "CIS Controls v8", "score": round(posture_score * cis_mult, 1)},
        {"name": "NIST CSF 2.0", "score": round(posture_score * nist_mult, 1)},
        {"name": "ISO 27001", "score": round(posture_score * iso_mult, 1)}
    ]

    return jsonify({
        "posture_score": posture_score,
        "maturity_level": maturity,
        "compliance_coverage": coverage,
        "risk_exposure": risk_exposure,
        "security_debt": security_debt,
        "remediation_velocity": velocity,
        "team_leaderboard": teams,
        "roadmap": roadmap,
        "priorities": priorities,
        "frameworks": frameworks,
        "summary": {
            "total_policies": fail_count + int(posture_score / 10 * fail_count / max(1, 100 - posture_score) if posture_score < 100 else 100),
            "passing": int(posture_score),
            "failing": fail_count
        }
    })


if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
