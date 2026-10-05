import os
import psycopg2
from psycopg2.extras import execute_values

class AuditLedgerDatabase:
    def __init__(self, db_config: dict = None):
        self.db_config = db_config or {
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "Redstone"),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432")
        }
        self.ensure_database_exists()
        self.setup_database()

    def ensure_database_exists(self):
        """Checks if pii_audit_db exists; if not, creates it using the default 'postgres' db."""
        target_db = "pii_audit_db"
        config = self.db_config.copy()
        config["dbname"] = "postgres"  # Connect to default postgres db first
        
        try:
            conn = psycopg2.connect(**config)
            conn.autocommit = True
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
                exists = cursor.fetchone()
                if not exists:
                    cursor.execute(f"CREATE DATABASE {target_db}")
                    print(f"[+] Database '{target_db}' created successfully.")
            conn.close()
        except Exception as e:
            print(f"[!] Error ensuring database exists: {e}")

    def get_connection(self):
        """Establishes a connection to the pii_audit_db database."""
        config = self.db_config.copy()
        config["dbname"] = "pii_audit_db"
        return psycopg2.connect(**config)

    def setup_database(self):
        """Initializes the PostgreSQL audit table if it does not already exist."""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS pii_audit_ledger (
            id SERIAL PRIMARY KEY,
            file_name VARCHAR(255) NOT NULL,
            location_marker VARCHAR(100) NOT NULL,
            entity_type VARCHAR(100) NOT NULL,
            original_value TEXT NOT NULL,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(create_table_query)
                    conn.commit()
            print("[+] PostgreSQL Audit Ledger table initialized successfully.")
        except Exception as e:
            print(f"[!] Database setup error: {e}")

    def log_entities(self, entities: list[dict]):
        """Batch inserts detected PII entities into the traceability ledger."""
        if not entities:
            return

        insert_query = """
        INSERT INTO pii_audit_ledger (file_name, location_marker, entity_type, original_value)
        VALUES %s
        """
        
        tuples = [
            (
                ent.get("file_name"),
                ent.get("location_marker"),
                ent.get("entity_type"),
                ent.get("original_value")
            )
            for ent in entities
        ]

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    execute_values(cursor, insert_query, tuples)
                    conn.commit()
            print(f"[+] Successfully logged {len(tuples)} PII entities to PostgreSQL ledger.")
        except Exception as e:
            print(f"[!] Error logging entities to database: {e}")