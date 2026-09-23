"""Conservative content indicators, not a certified DLP or PII detection engine."""

import re


def indicators(text: str) -> list[str]:
    rules = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b",
        "credential": (
            r"(?i)(?:api[_ -]?key|password|secret|token)\s*[:=]\s*[^\s,;]{6,}"
        ),
        "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    }
    return [name for name, pattern in rules.items() if re.search(pattern, text)]
