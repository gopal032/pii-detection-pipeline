from flask import Flask, request, render_template_string
import os

from ingestion.ingestion import pick_file_from_directory
from detection.detection import detect_and_redact

app = Flask(__name__)

FOLDER_PATH = "D:/Program/PIIProject/pii-detection-pipeline/sample_files"


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        uploaded_file = request.files.get("file")

        if uploaded_file:
            filename=uploaded_file.filename
            file_path = os.path.join(FOLDER_PATH, filename)
            uploaded_file.save(file_path)
    
        if filename.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            redacted, mapping = detect_and_redact(content)

            # Build mapping table HTML
            mapping_html = "<table border='1'><tr><th>Placeholder</th><th>Original Value</th></tr>"
            for placeholder, original in mapping.items():
                mapping_html += f"<tr><td>{placeholder}</td><td>{original}</td></tr>"
            mapping_html += "</table>"

            return f"""
                <h3>Selected File:</h3><p>{filename}</p>
                <h3>Original:</h3><pre>{content}</pre>
                <h3>Redacted:</h3><pre>{redacted}</pre>
                <h3>Mapping Table:</h3>{mapping_html}


            
            """
        else:
            return "Unsupported file type. Please upload a .txt file."
        
    html = """
    <form method="post" enctype="multipart/form-data">
        <label>Select a file:</label><br>
        <input type="file" name="file"><br><br>
        <input type="submit" value="Upload">
    </form>
    """
    return render_template_string(html)


if __name__ == "__main__":
    app.run(debug=True, port=8080)

