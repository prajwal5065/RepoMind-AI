import os
import zipfile
from typing import List

def extract_zip(zip_path: str, extract_to: str) -> None:
    """Extracts a zip file to the specified directory."""
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def list_files(directory: str) -> List[str]:
    """Lists all files in a directory recursively."""
    file_list = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_list.append(os.path.join(root, file))
    return file_list
