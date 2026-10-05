import os
from extractor import extract_document
from detector import PIIDetector
from database import AuditLedgerDatabase

def run_pii_pipeline(file_path: str):
    """
    End-to-end pipeline:
    1. Extracts text with structural traceability (slides/pages).
    2. Detects and redacts PII using Presidio.
    3. Logs structured PII findings into the PostgreSQL audit ledger.
    4. Protects downstream AI models with token-safe sanitized text.
    """
    if not os.path.exists(file_path):
        print(f"[!] Error: File not found at -> {file_path}")
        return

    print(f"\n[*] Starting PII Pipeline for: {os.path.basename(file_path)}")
    
    # 1. Initialize Extraction, Detection, and Database Ledger
    chunks = extract_document(file_path)
    print(f"[+] Extracted {len(chunks)} structural sections/pages.")
    
    detector = PIIDetector()
    db = AuditLedgerDatabase()
    
    all_audit_entries = []
    sanitized_document_output = []

    # 2. Process each chunk through the detection engine
    for chunk in chunks:
        file_name = chunk["file_name"]
        location = chunk["location_marker"]
        raw_content = chunk["content"]
        
        # Scan and redact
        redacted_text, detected_entities = detector.scan_and_redact(raw_content)
        
        # Enrich entities with source traceability metadata
        for entity in detected_entities:
            entity["file_name"] = file_name
            entity["location_marker"] = location
            all_audit_entries.append(entity)
            
        sanitized_document_output.append({
            "location": location,
            "sanitized_text": redacted_text
        })

    # 3. Log findings into the PostgreSQL audit ledger for Cadence internal compliance
    if all_audit_entries:
        print(f"[+] Detected {len(all_audit_entries)} PII instance(s). Writing to PostgreSQL audit ledger...")
        db.log_entities(all_audit_entries)
    else:
        print("[+] No PII detected in this document.")

    print(f"[+] Pipeline complete. Sanitized payload is safe for downstream AI model consumption.")
    return sanitized_document_output

if __name__ == "__main__":
    # Test run using your benchmark files (e.g., Cadence Risk Policy or Org Pack)
    # Ensure your sample document is placed in the project directory, then uncomment:
    
    sample_doc = "Cadence_Financial_Group_Organizational_Pack.pptx"
    run_pii_pipeline(sample_doc)
    
    pass