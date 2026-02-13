import os
import sqlite3

def reinit_db():
    db_path = 'compliance.db'
    schema_path = 'schema.sql'
    
    print(f"🗑️  Starting database reinitialization for '{db_path}'...")
    
    # 1. Close connections if possible (not needed here but good practice)
    # 2. Delete existing database file
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            print(f"✅ Deleted existing database: {db_path}")
        except Exception as e:
            print(f"❌ Error deleting database: {e}")
            return
    
    # 3. Create fresh database
    try:
        if not os.path.exists(schema_path):
            print(f"❌ Error: Schema file '{schema_path}' not found!")
            return
            
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
            
        conn = sqlite3.connect(db_path)
        conn.executescript(schema_sql)
        
        # Insert default configuration values
        print("📋 Inserting default configuration values...")
        defaults = [
            ('impact_high_threshold', '5', 'Fail count threshold for High impact classification'),
            ('impact_medium_threshold', '2', 'Fail count threshold for Medium impact classification'),
            ('effort_low_keywords', '["Ensure", "Set"]', 'Keywords indicating low effort policies (JSON array)'),
            ('effort_high_keywords', '["Manual", "Review"]', 'Keywords indicating high effort policies (JSON array)'),
            ('security_debt_hours_per_issue', '0.5', 'Hours of security debt per failing policy'),
            ('risk_exposure_multiplier', '2', 'Multiplier for risk exposure calculation'),
            ('framework_cis_multiplier', '0.95', 'CIS Controls v8 alignment multiplier'),
            ('framework_nist_multiplier', '0.88', 'NIST CSF 2.0 alignment multiplier'),
            ('framework_iso_multiplier', '0.82', 'ISO 27001 alignment multiplier')
        ]
        
        cursor = conn.cursor()
        cursor.executemany(
            'INSERT OR IGNORE INTO config_settings (key, value, description) VALUES (?, ?, ?)',
            defaults
        )
        
        conn.commit()
        conn.close()
        
        print(f"✨ Successfully reinitialized database from '{schema_path}'!")
        print(f"📍 Database location: {os.path.abspath(db_path)}")
        
    except Exception as e:
        print(f"❌ Error during reinitialization: {e}")

if __name__ == "__main__":
    # Ensure we are in the backend directory
    current_dir = os.getcwd()
    if not current_dir.endswith('backend'):
        # Try to find the backend dir
        if os.path.exists('backend'):
            os.chdir('backend')
        else:
            print("⚠️  Warning: Script should be run from the 'backend' directory.")
            
    reinit_db()
