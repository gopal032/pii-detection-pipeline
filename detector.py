import re

class PIIDetector:
    def __init__(self):
        # Define regex patterns for structured PII matching Cadence benchmark data
        self.patterns = {
            "EMPLOYEE_ID": r"\bEMP-\d{5}\b",
            "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "PHONE": r"(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*(?:[.-]\s*)?([0-9]{4})(?:\s*(?:#|x\.?|ext\.?|extension)\s*(\d+))?", # North American format
            "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
            "PAN": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",          # Indian PAN card format
            "PASSPORT": r"\b[A-Z]{2}\d{7}\b",             # Common international passport format
            "PESEL": r"\b\d{11}\b"                       # Polish PESEL format
        }

    def scan_and_redact(self, text: str) -> tuple[str, list[dict]]:
        """
        Scans text for PII patterns, applies transparent tags, 
        and records findings for the traceability ledger.
        """
        detected_entities = []
        redacted_text = text

        for entity_type, pattern in self.patterns.items():
            matches = list(re.finditer(pattern, redacted_text))
            # Iterate in reverse to avoid index shifting during replacement
            for match in reversed(matches):
                original_value = match.group(0)
                start, end = match.span()
                tag = f"[{entity_type}]"
                
                # Apply transparent tag
                redacted_text = redacted_text[:start] + tag + redacted_text[end:]
                
                # Record entity for audit trail
                detected_entities.append({
                    "entity_type": entity_type,
                    "original_value": original_value,
                    "start_pos": start,
                    "end_pos": end
                })

        return redacted_text, detected_entities