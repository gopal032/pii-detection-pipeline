from ingestion.ingestion import pick_file_from_directory
folder = "D:/Program/PIIProject/pii-detection-pipeline/sample_files"  # change to your folder path

file_path = pick_file_from_directory(folder)
print("Selected file:", file_path)