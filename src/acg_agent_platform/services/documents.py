"""Bound file size and parser runtime before accepting extracted knowledge."""

import base64
import binascii
import json
import subprocess
import sys
from pathlib import Path

from acg_agent_platform.models.platform import ExtractDocument


def extract_document(body: ExtractDocument) -> str:
    extension = Path(body.filename).suffix.lower()
    if extension not in {".txt", ".md", ".csv", ".json", ".log", ".eml", ".pdf"}:
        raise ValueError("Unsupported document format")
    try:
        data = base64.b64decode(body.data_base64, validate=True)
    except binascii.Error as exc:
        raise ValueError("Invalid file encoding") from exc
    if len(data) > 1_000_000:
        raise ValueError("Document exceeds 1 MB pilot limit")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "acg_agent_platform.services.document_worker",
                extension,
            ],
            input=data,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Document parsing timed out") from exc
    if result.returncode or len(result.stdout) > 150000:
        raise ValueError("Document rejected; scanned PDFs need OCR")
    output = json.loads(result.stdout)
    return str(output["text"])
