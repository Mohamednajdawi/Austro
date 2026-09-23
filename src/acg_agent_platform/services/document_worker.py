"""Short-lived parsing worker; no model calls or document-controlled network access."""

import json
import sys
from email import policy
from email.parser import BytesParser
from io import BytesIO

from pypdf import PdfReader


def extract(data: bytes, extension: str) -> str:
    if extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("Not a PDF")
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted or len(reader.pages) > 20:
            raise ValueError("Encrypted or oversized PDF")
        parts = []
        for page in reader.pages:
            contents = page.get_contents()
            if contents is not None and len(contents.get_data()) > 2_000_000:
                raise ValueError("PDF stream too large")
            parts.append(page.extract_text() or "")
        text = "\n".join(parts)
    elif extension == ".eml":
        message = BytesParser(policy=policy.default).parsebytes(data)
        body = message.get_body(preferencelist=("plain",))
        text = str(body.get_content()) if body else ""
    else:
        text = data.decode("utf-8-sig", errors="strict")
    if not text.strip() or len(text) > 20000 or "\x00" in text:
        raise ValueError("Empty, binary or oversized text; scanned PDFs require OCR")
    return text


def main() -> None:
    try:
        text = extract(sys.stdin.buffer.read(1_000_001), sys.argv[1])
        sys.stdout.write(json.dumps({"text": text}))
    except Exception:
        # Isolated parser boundary: never expose file internals or raw parser errors.
        sys.stdout.write(
            json.dumps(
                {"error": "Document rejected; use text PDF, UTF-8 text or plain EML"}
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
