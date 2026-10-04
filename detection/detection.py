import re
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer

# Initialize Engine ONCE at the module level
analyzer = AnalyzerEngine()

# Add Custom Phone Recognizer directly to registry
phone_pattern = Pattern(
    name="indian_int_phone",
    regex=r"(?:\+?91[\s.-]*)?[6-9]\d{4}[\s.-]*\d{5}|\+?\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{3,5}[\s.-]?\d{4,5}",
    score=1.0,
)
analyzer.registry.add_recognizer(
    PatternRecognizer(
        supported_entity="PHONE_NUMBER", patterns=[phone_pattern]
    )
)

# Add Custom LinkedIn / URL Recognizer
url_pattern = Pattern(
    name="custom_url_pattern",
    regex=r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+/?|(?:https?://|www\.)[a-zA-Z0-9.\-]+(?::\d+)?(?:/[^\s]*)?",
    score=1.0,
)
analyzer.registry.add_recognizer(
    PatternRecognizer(supported_entity="URL", patterns=[url_pattern])
)

# Whitelist broad countries to avoid redacting general geographies
COUNTRY_WHITELIST = {
    "us",
    "usa",
    "united states",
    "canada",
    "uk",
    "united kingdom",
    "india",
    "germany",
    "finland",
}


def normalize_text(text):
    """Clean hidden non-breaking spaces and unicode artifacts from PPT/PDFs."""
    text = re.sub(r"[\xa0\u200b\u200e\u200f\u202f]", " ", text)
    return text


def filter_false_positives(results, text):
    """Filter out invalid DATE_TIME and LOCATION entities."""
    filtered = []

    # Regex to catch durations (e.g., '25+ years', '30 years')
    duration_regex = re.compile(
        r"\b(\d+\+?\s*(years?|months?|yrs?)|nearly\s*\d+\s*years?)\b",
        re.IGNORECASE,
    )

    # Matches standalone 4-digit calendar years (1900 - 2099)
    standalone_year_regex = re.compile(r"^\b(19|20)\d{2}\b$")
  

    # Regex to catch phone digits misclassified as DATE_TIME
    phone_digits_regex = re.compile(r"^\+?\d[\d\s.-]{7,14}\d$")

    for res in results:
        entity_text = text[res.start : res.end].strip()
        entity_lower = entity_text.lower()

        # Reject DATE_TIME tags if they are actually work experience or phone digits
        if res.entity_type == "DATE_TIME":
            if duration_regex.search(entity_text) or phone_digits_regex.match(
                entity_text
            ):
                continue
            if standalone_year_regex.match(entity_text):
                continue


        # Reject LOCATION tags if they are generic nouns or whitelisted countries
        if res.entity_type == "LOCATION":
            if (
                entity_lower in ["geographies", "global", "world"]
                or entity_lower in COUNTRY_WHITELIST
            ):
                continue
        
        if res.entity_type == "DATE_TIME":
            # 1. Ignore work experience durations ("25+ years")
            if duration_regex.search(entity_text):
                continue
            # 2. Ignore standalone 4-digit award/calendar years (2023, 2021, 2014, 2010)
            if standalone_year_regex.match(entity_text):
                continue

        filtered.append(res)
    return filtered


def filter_overlapping_results(results):
    """Resolve overlaps by keeping highest scoring and longest entity matches."""
    sorted_res = sorted(
        results, key=lambda r: (r.score, r.end - r.start), reverse=True
    )
    keep = []
    for res in sorted_res:
        if not any(
            max(res.start, k.start) < min(res.end, k.end) for k in keep
        ):
            keep.append(res)
    return sorted(keep, key=lambda x: x.start)


def detect_and_redact(text):
    text = normalize_text(text)

    supported_entities = [
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "PERSON",
        "LOCATION",
        "IP_ADDRESS",
        "DATE_TIME",
        "URL",
    ]

    results = analyzer.analyze(
        text=text,
        entities=supported_entities,
        language="en",
        score_threshold=0.2,
    )

    valid_results = filter_false_positives(results, text)
    clean_results = filter_overlapping_results(valid_results)

    entity_counters = {}
    value_to_placeholder = {}  # Cache to deduplicate identical entity values
    redactions = []

    for res in clean_results:
        entity_type = res.entity_type
        entity_val = text[res.start : res.end].strip()

# Check if this exact text value has already been assigned a placeholder
        if entity_val in value_to_placeholder:
            placeholder = value_to_placeholder[entity_val]
        else:
            entity_counters[entity_type] = entity_counters.get(entity_type, 0) + 1

            label = (
                entity_type.replace("_ADDRESS", "")
                .replace("_NUMBER", "")
                .replace("_TIME", "")
            )
            placeholder = f"[{label}_{entity_counters[entity_type]}]"
            value_to_placeholder[entity_val] = placeholder
        

        redactions.append(
            {
                "start": res.start,
                "end": res.end,
                "placeholder": placeholder,
                "original": text[res.start : res.end].strip(),
            }
        )

    redacted_text = text
    for item in sorted(redactions, key=lambda x: x["start"], reverse=True):
        redacted_text = (
            redacted_text[: item["start"]]
            + item["placeholder"]
            + redacted_text[item["end"] :]
        )

    mapping = {item["placeholder"]: item["original"] for item in redactions}
    return redacted_text, mapping