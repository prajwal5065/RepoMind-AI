"""
File utility helpers.

Security note
-------------
``extract_zip`` validates every member path against the extraction root
before writing to disk, preventing Zip Slip attacks (CWE-22).
"""
import os
import zipfile
from typing import List


def extract_zip(zip_path: str, extract_to: str) -> None:
    """
    Extract a zip archive to *extract_to*, blocking Zip Slip attacks.

    Each member's resolved output path is checked to ensure it stays
    inside *extract_to*. Any member that would escape the directory
    raises ``ValueError`` and the partial extraction is aborted.
    """
    extract_root = os.path.realpath(extract_to)
    os.makedirs(extract_root, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            # Resolve where this member would land on disk.
            target = os.path.realpath(os.path.join(extract_root, member.filename))

            # Block any path that escapes the extraction directory.
            if not (target == extract_root or target.startswith(extract_root + os.sep)):
                raise ValueError(
                    f"Zip Slip blocked: '{member.filename}' would extract outside "
                    f"the target directory."
                )

            zf.extract(member, extract_root)


def list_files(directory: str) -> List[str]:
    """List all files in *directory* recursively. Returns absolute paths."""
    file_list = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_list.append(os.path.join(root, file))
    return file_list
