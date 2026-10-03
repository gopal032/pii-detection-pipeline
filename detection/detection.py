from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from sqlalchemy import text

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()



def detect_and_redact(text):

    
    results = analyzer.analyze(
        text=text,
        entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "PERSON","LOCATION","NRP","IP_ADDRESS","DATE_TIME","URL"],
        language="en",
        score_threshold=0.2,
    )


    operators = {
        "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL]"}),
        "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
    }

    anonymized_text = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators,
    )

    # Build mapping dictionary: placeholder → original value
    mapping = {}
    #generate unique placeholders for each detected entity
    entity_counters = {}
    redactions = []


    for res in sorted(results, key=lambda x: x.start):
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

    # 2. Build mapping dictionary with unique keys
    mapping = {item["placeholder"]: item["original"] for item in redactions}

    #3. Replace text in reverse order so character offsets stay valid

    redacted_text = text
    for item in sorted(redactions, key=lambda x: x["start"], reverse=True):
        redacted_text = (
            redacted_text[: item["start"]]
            + item["placeholder"]
            + redacted_text[item["end"] :]
        )


    return redacted_text, mapping
