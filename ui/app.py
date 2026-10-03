import os
from flask import Flask, render_template_string, request
from ingestion.document_handler import DocumentHandlerFactory

app = Flask(__name__)

FOLDER_PATH = "D:/Program/PIIProject/pii-detection-pipeline/sample_files"
os.makedirs(FOLDER_PATH, exist_ok=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document Inspection Studio</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border-color: #e2e8f0;
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', sans-serif; background-color: var(--bg-color); color: var(--text-main); padding: 24px; }
        
        .header { margin-bottom: 20px; }
        .header h1 { font-size: 1.5rem; font-weight: 700; color: #1e293b; }
        
        .upload-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 16px 24px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .upload-form { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
        .file-input { border: 1px solid var(--border-color); padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; background: #fff; }
        .btn-submit { background-color: var(--primary); color: white; border: none; padding: 9px 20px; border-radius: 6px; font-weight: 500; cursor: pointer; transition: background 0.2s; }
        .btn-submit:hover { background-color: var(--primary-hover); }

        /* Metadata Header Badges */
        .meta-container { display: flex; gap: 12px; margin-top: 12px; flex-wrap: wrap; }
        .meta-badge { background: #f1f5f9; border: 1px solid var(--border-color); color: #334155; padding: 6px 14px; border-radius: 8px; font-size: 0.85rem; font-weight: 500; }
        .meta-badge strong { color: #0f172a; }

        /* Split Workspace */
        .workspace { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .pane { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .pane-header { background: #f1f5f9; padding: 12px 20px; border-bottom: 1px solid var(--border-color); font-weight: 600; font-size: 0.95rem; color: #334155; display: flex; justify-content: space-between; }
        .pane-body { padding: 20px; height: 500px; overflow-y: auto; font-family: 'Fira Code', monospace; font-size: 0.88rem; line-height: 1.6; white-space: pre-wrap; word-break: break-all; background: #fafafa; }
        
        .error-box { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; }
        .empty-state { text-align: center; color: var(--text-muted); padding: 40px 20px; }
    </style>
</head>
<body>

    <div class="header">
        <h1>Document Inspection Studio</h1>
    </div>

    {% if error %}
    <div class="error-box">
        <strong>Error:</strong> {{ error }}
    </div>
    {% endif %}

    <div class="upload-card">
        <form class="upload-form" method="post" enctype="multipart/form-data">
            <input class="file-input" type="file" name="file" required>
            <button class="btn-submit" type="submit">Inspect Document</button>
        </form>

        {% if file_info %}
        <div class="meta-container">
            <div class="meta-badge"><strong>Active File Name:</strong> {{ file_info.filename }}</div>
            <div class="meta-badge"><strong>Active File Type:</strong> {{ file_info.file_type }}</div>
            <div class="meta-badge"><strong>Total Number of Pages:</strong> {{ file_info.page_count }}</div>
        </div>
        {% endif %}
    </div>

    {% if file_info %}
    <div class="workspace">
        <div class="pane">
            <div class="pane-header">
                <span>Original Document Preview</span>
            </div>
            <div class="pane-body">{{ file_info.content }}</div>
        </div>

        <div class="pane">
            <div class="pane-header">
                <span>Redacted Document</span>
            </div>
            <div class="pane-body empty-state">
                [ Waiting for next step: Redaction API not invoked ]
            </div>
        </div>
    </div>
    {% else %}
    <div class="upload-card empty-state">
        Upload a file (.txt, .pdf, .docx, or Image) to inspect its type, page count, and content.
    </div>
    {% endif %}

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
                # Obtain appropriate OO handler instance
                handler = DocumentHandlerFactory.get_handler(file_path)

                file_info = {
                    "filename": handler.filename,
                    "file_type": handler.get_file_type(),
                    "page_count": handler.get_page_count(),
                    "content": handler.get_content_preview(),
                }
            except Exception as e:
                error = str(e)

    return render_template_string(HTML_TEMPLATE, file_info=file_info, error=error)


if __name__ == "__main__":
    app.run(debug=True, port=8080)