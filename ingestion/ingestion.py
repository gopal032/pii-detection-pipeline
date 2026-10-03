import os


def pick_file_from_directory(directory):
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    if not files:
        return None
    print("Available files:")
    for idx, file in enumerate(files):
        print(f"{idx + 1}: {file}")
    choice = int(input("Select a file by number: ")) - 1
    if 0 <= choice < len(files):
        return os.path.join(directory, files[choice])
    else:
        print("Invalid selection.")
        return None