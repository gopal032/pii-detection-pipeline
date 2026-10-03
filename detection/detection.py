from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer

analyzer = AnalyzerEngine()

# Custom regex pattern for credit cards (handles spaces/hyphens without requiring Luhn)
card_pattern = Pattern(
    name="credit_card_pattern",
    regex=r"\b(?:\d[ -]*?){13,19}\b",
    score=0.85,
)
custom_card_recognizer = PatternRecognizer(
    supported_entity="CREDIT_CARD",
    patterns=[card_pattern],
)
analyzer.registry.add_recognizer(custom_card_recognizer)


def filter_overlapping_results(results):
    """Filter out overlapping entity detections, keeping higher score/longer matches."""
    # Sort by score (descending), then by span length (descending)
    sorted_res = sorted(
        results, key=lambda r: (r.score, r.end - r.start), reverse=True
    )

    keep = []
    for res in sorted_res:
        # Check if this result overlaps with any higher-priority result already kept
        if not any(
            max(res.start, k.start) < min(res.end, k.end) for k in keep
        ):
            keep.append(res)

    return sorted(keep, key=lambda x: x.start)


def detect_and_redact(text):
    supported_entities = [
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "PERSON",
        "LOCATION",
        "IP_ADDRESS",
        "DATE_TIME",
        "US_SSN",
    ]

    results = analyzer.analyze(
        text=text,
        entities=supported_entities,
        language="en",
        score_threshold=0.2,
    )

    # 1. Resolve overlaps so character offsets don't corrupt each other
    clean_results = filter_overlapping_results(results)

    # 2. Build unique placeholders
    entity_counters = {}
    redactions = []

    for res in clean_results:
        entity_type = res.entity_type
        entity_counters[entity_type] = entity_counters.get(entity_type, 0) + 1

        label = entity_type.replace("_ADDRESS", "").replace("_NUMBER", "")
        placeholder = f"[{label}_{entity_counters[entity_type]}]"

        redactions.append(
            {
                "start": res.start,
                "end": res.end,
                "placeholder": placeholder,
                "original": text[res.start : res.end],
            }
        )

    mapping = {item["placeholder"]: item["original"] for item in redactions}

    # 3. Replace text from back-to-front using clean offsets
    redacted_text = text
    for item in sorted(redactions, key=lambda x: x["start"], reverse=True):
        redacted_text = (
            redacted_text[: item["start"]]
            + item["placeholder"]
            + redacted_text[item["end"] :]
        )

    return redacted_text, mapping