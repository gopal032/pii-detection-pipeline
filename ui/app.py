import os
from db.repository import init_db, save_processed_document_to_db
from detection.detection import detect_and_redact
from flask import Flask, render_template_string, request
from ingestion.document_handler import DocumentHandlerFactory

app = Flask(__name__)

FOLDER_PATH = "D:/Program/PIIProject/pii-detection-pipeline/sample_files"
os.makedirs(FOLDER_PATH, exist_ok=True)

try:
  init_db()
  print("PostgreSQL Database tables verified/initialized successfully.")
except Exception as db_err:
  print(f"Warning: PostgreSQL DB Connection failed: {db_err}")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PII Redaction Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f4f6f9; color: #333; }
        .container { max-width: 1200px; margin: auto; }
        
        /* Upload & Error Styles */
        .upload-card { background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .error { background: #ffe6e6; color: #d9534f; padding: 10px; border-radius: 5px; margin-bottom: 15px; }

        /* Metadata Box Styles */
        .metadata-box { 
            background: #fff; 
            padding: 15px 20px; 
            border-radius: 8px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
            margin-bottom: 20px; 
            display: flex; 
            gap: 30px; 
            font-size: 14px; 
        }
        .metadata-box div span { font-weight: bold; color: #007bff; }

        /* Side-by-side previews with scrolling enabled */
        .preview-wrapper { display: flex; gap: 20px; margin-bottom: 25px; }
        .pane { 
            flex: 1; 
            background: #fff; 
            padding: 20px; 
            border-radius: 8px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
            max-height: 450px; 
            overflow-y: auto; 
        }
        pre { white-space: pre-wrap; word-wrap: break-word; font-family: monospace; font-size: 13px; margin: 0; }

        /* Scrollable PII Mapping Table Styles with Borders Across Rows and Columns */
        .mapping-card {
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 25px;
        }
        .table-container {
            max-height: 250px; /* Enables vertical scrolling */
            overflow-y: auto;
            border: 1px solid #ccc;
            border-radius: 6px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 14px;
            border: 1px solid #ccc;
        }
        th, td {
            padding: 10px 15px;
            border: 1px solid #ccc; /* Border across each row and column */
        }
        th {
            background: #f1f3f5;
            position: sticky;
            top: 0;
            z-index: 1;
        }
        tr:hover { background: #f8f9fa; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Document PII Redaction Dashboard</h2>

        <!-- File Upload Form -->
        <div class="upload-card">
            <form method="POST" enctype="multipart/form-data" style="margin: 0;">
                <input type="file" name="file" required>
                <button type="submit" style="padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">Redact Document</button>
            </form>
        </div>

        {% if error %}
        <div class="error"><strong>Error:</strong> {{ error }}</div>
        {% endif %}

        {% if file_info %}
        <!-- File Metadata Information -->
        <div class="metadata-box">
            <div>File Name: <span>{{ file_info.filename }}</span></div>
            <div>File Type: <span>{{ file_info.file_type }}</span></div>
            <div>Total Pages: <span>{{ file_info.page_count }}</span></div>
            <div>Status: <span>{{ file_info.status }}</span></div>
            <div>Detected Entities: <span>{{ file_info.total_entities }}</span></div>
        </div>
        {% endif %}

        <!-- 1. Side-by-Side Document Previews (Scroll Enabled) -->
        <div class="preview-wrapper">
            <div class="pane">
                <h3>Original Document Preview</h3>
                <pre>{{ file_info.raw_content if file_info else 'Upload a document to view original content...' }}</pre>
            </div>
            <div class="pane">
                <h3>Redacted Output</h3>
                <pre>{{ file_info.redacted_content if file_info else 'Upload a document to view redacted output...' }}</pre>
            </div>
        </div>

        <!-- 2. PII Mapping Table (Positioned Below Previews with Full Borders & Scrolling) -->
        {% if file_info and file_info.combined_mapping %}
        <div class="mapping-card">
            <h3>Detected PII Mapping Reference</h3>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Placeholder</th>
                            <th>Original Entity Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for placeholder, original in file_info.combined_mapping.items() %}
                        <tr>
                            <td><code>{{ placeholder }}</code></td>
                            <td>{{ original }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():
  file_info = None
  error = None

  if request.method == "POST":
    uploaded_file = request.files.get("file")

    if uploaded_file and uploaded_file.filename != "":
      filename = uploaded_file.filename
      file_path = os.path.join(FOLDER_PATH, filename)
      uploaded_file.save(file_path)

      try:
        handler = DocumentHandlerFactory.get_handler(file_path)
        pages_text = handler.get_pages_text()

        pages_processed = []
        combined_mapping = {}

        for raw_text in pages_text:
          redacted_text, mapping = detect_and_redact(raw_text)
          pages_processed.append(
              {
                  "raw_text": raw_text,
                  "redacted_text": redacted_text,
                  "mapping": mapping,
              }
          )
          combined_mapping.update(mapping)

        # Persist to PostgreSQL database
        doc_record = save_processed_document_to_db(
            handler, file_path, pages_processed
        )

        file_info = {
            "doc_id": str(doc_record.id),
            "filename": doc_record.filename,
            "file_type": doc_record.file_type,
            "page_count": doc_record.total_pages,
            "status": doc_record.status,
            "total_entities": len(combined_mapping),
            "combined_mapping": combined_mapping,
            "raw_content": "\n\n--- PAGE BREAK ---\n\n".join(
                [p["raw_text"] for p in pages_processed]
            ),
            "redacted_content": "\n\n--- PAGE BREAK ---\n\n".join(
                [p["redacted_text"] for p in pages_processed]
            ),
        }
      except Exception as e:
        error = str(e)

  return render_template_string(
      HTML_TEMPLATE, file_info=file_info, error=error
  )


if __name__ == "__main__":
  app.run(debug=True, port=8080)