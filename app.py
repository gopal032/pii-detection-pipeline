import streamlit as st
import os
from extractor import extract_document
from detector import PIIDetector
from database import AuditLedgerDatabase  # <-- Updated to match your database.py file

# Page Configuration
st.set_page_config(
    page_title="Cadence Enterprise PII Firewall",
    page_icon="🛡",
    layout="wide"
)

st.title("🛡️ Cadence Financial Group: Enterprise PII Firewall & Audit Ledger")
st.markdown("Upload enterprise documents (.pptx or .pdf) to enforce PII masking, secure traceability, and database auditing.")

# File Uploader
uploaded_file = st.file_uploader("Upload Organizational Pack or Risk Policy", type=["pptx", "pdf"])

if uploaded_file is not None:
    temp_dir = "./temp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, uploaded_file.name)
    
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    st.success(f"File uploaded successfully: **{uploaded_file.name}**")
    
    if st.button("🚀 Run PII Redaction & Audit Pipeline", type="primary"):
        with st.spinner("Processing document through extraction, Presidio detection, and PostgreSQL ledger..."):
            try:
                # 1. Extract text chunks
                chunks = extract_document(temp_path)
                
                # 2. Initialize Detector & Database Ledger
                detector = PIIDetector()
                db = AuditLedgerDatabase()  # <-- Using your database.py class
                
                all_audit_entries = []
                sanitized_document_output = []
                
                # 3. Process chunks
                for chunk in chunks:
                    file_name = chunk["file_name"]
                    location = chunk["location_marker"]
                    raw_content = chunk["content"]
                    
                    redacted_text, detected_entities = detector.scan_and_redact(raw_content)
                    
                    for entity in detected_entities:
                        entity["file_name"] = file_name
                        entity["location_marker"] = location
                        all_audit_entries.append(entity)
                        
                    sanitized_document_output.append({
                        "location": location,
                        "sanitized_text": redacted_text
                    })
                
                # 4. Log to PostgreSQL using your database.py method
                if all_audit_entries:
                    db.log_entities(all_audit_entries)
                
                st.toast(f"Pipeline complete! Found {len(all_audit_entries)} PII instances.", icon="✅")
                
                # Layout Results into Columns
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 Detected PII Audit Log")
                    if all_audit_entries:
                        st.dataframe(all_audit_entries, use_container_width=True)
                    else:
                        st.info("No PII detected in this document.")
                        
                with col2:
                    st.subheader("🔒 Sanitized AI Payload Preview")
                    for section in sanitized_document_output[:5]: # Preview first 5 sections
                        with st.expander(f"Location: {section['location']}"):
                            st.text(section['sanitized_text'])
                            
            except Exception as e:
                st.error(f"Pipeline execution error: {e}")