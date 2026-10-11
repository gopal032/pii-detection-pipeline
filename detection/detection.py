import re
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult,RecognizerRegistry

# Initialize Engine ONCE at the module level
# analyzer = AnalyzerEngine()
# Define custom whitelisted words or context words to prevent false positives
# e.g., suppress 'A common', 'A quorum', etc. from being flagged as PERSON
registry = RecognizerRegistry()
registry.load_predefined_recognizers()
analyzer = AnalyzerEngine(registry=registry)

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

# US-style numbers with a bracketed area code, e.g. "+1 (555) 0114" / "(555) 123-4567"
us_phone_pattern = Pattern(
    name="bracketed_area_code_phone",
    regex=r"\+?\d{1,3}[ .-]?\(\d{2,4}\)[ .-]?\d{3,4}(?:[ .-]\d{3,4})?",
    score=1.0,
)
analyzer.registry.add_recognizer(
    PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=[us_phone_pattern])
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

# Email recognizer that accepts ANY top-level domain (the built-in one rejects
# unknown TLDs such as ".example"), so addresses are not left half-detected as URLs.
email_pattern = Pattern(
    name="any_tld_email",
    regex=r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    score=1.0,
)
analyzer.registry.add_recognizer(
    PatternRecognizer(supported_entity="EMAIL_ADDRESS", patterns=[email_pattern])
)

# "A. Okonkwo-Bell", "E. Bertucci": initial + surname, which spaCy often misses
initial_name_pattern = Pattern(
    name="initial_surname",
    regex=r"\b[A-Z]\.[ \t]?(?!(?:The|This|That|These|Those|In|If|It|For|To|On|At|As|An|And|But|Or|We|Our|You|Please|Each|All|Any|Once|When|Where|Which|Not|No|Yes|Note|See|Use|Add|Click|Select|Enter|Set|Open|Ensure|After|Before|Then|Also)\b)[A-Z][a-z]+(?:['-][A-Z][a-z]+)*\b",
    score=0.95,
)
analyzer.registry.add_recognizer(
    PatternRecognizer(supported_entity="PERSON", patterns=[initial_name_pattern])
)


# ---------------------------------------------------------------------------
# Identifier recognizers (these also matter for OCR'd scans, where text layout
# is noisy and the NER model sees less context)
# ---------------------------------------------------------------------------
def _add(entity, name, regex, score):
    analyzer.registry.add_recognizer(
        PatternRecognizer(
            supported_entity=entity,
            patterns=[Pattern(name=name, regex=regex, score=score)],
        )
    )

# US SSN in 3-2-4 form. Presidio's built-in rule rejects 9xx numbers, which are common in test data.
_add("US_SSN", "ssn_3_2_4", r"\b\d{3}-\d{2}-\d{4}\b", 0.9)
# Indian PAN, e.g. AQBPR7741L
_add("IN_PAN", "pan", r"\b[A-Z]{5}\d{4}[A-Z]\b", 0.9)
# Passport numbers when introduced by the word "passport"
_add("PASSPORT", "passport_ctx", r"(?i:passport)(?:[ \t]+(?i:no\.?|number|#))?[ \t:]*[A-Z]{1,2}\d{6,9}\b", 0.9)
# Employee identifiers such as EMP-38104
_add("EMPLOYEE_ID", "emp_id", r"(?<![A-Za-z0-9])EMP-(?:[A-Z]{2}-)?\d{3,5}(?!\d)", 0.9)
# Director identifiers such as DIR-0042
_add("DIRECTOR_ID", "dir_id", r"(?<![A-Za-z0-9])DIR-(?:[A-Z]{2}-)?\d{3,5}(?!\d)", 0.9)
# Vendor identifiers such as MER-IN-4471
_add("VENDOR_ID", "vendor_id", r"(?<![A-Za-z0-9])MER-(?:[A-Z]{2}-)?\d{3,5}(?!\d)", 0.9)

# Street addresses: "88 Willowbank Court, Hoboken, NJ 07030", "1180 Ashwood Lane, Apartment 4C, ..."
_add(
    "STREET_ADDRESS",
    "us_street_address",
    r"\b\d{1,5}[ \t]+(?:[A-Z][A-Za-z.'-]+[ \t]+){1,3}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Court|Ct|Crescent|Drive|Dr|Boulevard|Blvd|Way|Place|Pl|Terrace|Square)\b\.?"
    r"(?:,?[ \t]*(?:Apartment|Apt|Suite|Ste|Unit|Floor)[ \t]*[\w-]+)?"
    r"(?:,[ \t]*[A-Z][A-Za-z.' -]+?)?"
    r"(?:,[ \t]*[A-Z]{2}[ \t]+\d{5}(?:-\d{4})?)?",
    0.85,
)
# Names introduced by a title: "Ms Prieto-Ramos", "Dr. Jane Smith"
_add(
    "PERSON",
    "titled_name",
    r"\b(?:Mr|Mrs|Ms|Miss|Mx|Dr|Prof)\.?[ \t]+[A-Z][a-z]+(?:[-'][A-Z][a-z]+)*(?:[ \t]+[A-Z][a-z]+(?:[-'][A-Z][a-z]+)*)?\b",
    0.9,
)
# A country/area prefix that is NOT followed by digits is a fragment of a split number
_add("PHONE_NUMBER", "phone_prefix_no_tail_a", r"\+\d{1,3}[ ]?\(\d{2,4}\)(?![ \t.-]*\d)", 0.8)
_add("PHONE_NUMBER", "phone_prefix_no_tail_b", r"\+\d{1,3}[ ]\d{2,3}(?![ \t.-]*\d)", 0.7)
_add("PHONE_NUMBER", "phone_prefix_no_tail_c", r"\+\d{3,4}(?![ \t.-]*\d)", 0.7)
# "555-0121" sitting on its own inside a table cell (tail of a wrapped number)
_add("PHONE_NUMBER", "phone_tail_dash", r"(?<![\w-])\d{3}-\d{4}(?![\w-])", 0.7)
# "Gregor Halvorsen (EMP-35440)": a name directly followed by an employee ID
_add(
    "PERSON",
    "name_before_emp_id",
    r"\b[A-Z][a-z]+(?:[ \t]+[A-Z]\.){0,2}[ \t]+[A-Z][a-z]+(?:[-'][A-Z][a-z]+)*(?=[ \t]*[\(\u2014,-]*[ \t]*(?:EMP|DIR|MER)-)",
    0.9,
)
# Fragments of phone numbers left behind when a table cell wraps onto several lines:
#  "+1 (704)      Yusuf O. Balogun ...\n555-0166"  /  "+91 80      Ananya ...\n4555 0182"
_add("PHONE_NUMBER", "phone_prefix_fragment", r"\+\d{1,3}[ ]?\(?\d{2,5}\)?(?=[ \t]{2,}\S|[ \t]*$)", 0.8)
_add("PHONE_NUMBER", "phone_tail_fragment_a", r"(?m)^[ \t]*\d{3}[ -]\d{4}[ \t]*(?=\s|$)", 0.7)
_add("PHONE_NUMBER", "phone_tail_fragment_c", r"(?m)^[ \t]*\d{5}[ \t]*(?=\s|$)", 0.6)
_add("PHONE_NUMBER", "phone_tail_fragment_b", r"(?m)^[ \t]*\d{4}[ ]?\d{4}[ \t]*(?=\s|$)", 0.7)

# Frequency words that the date recognizer wrongly tags as DATE_TIME
FREQUENCY_WORDS = {
    "annual", "annually", "quarterly", "monthly", "weekly", "daily",
    "yearly", "biannual", "semi-annual", "semiannual", "biannually",
}


# Product / company / UI words that the NER model wrongly labels as PERSON.
# Add your own organisation and tool names here.
NON_PERSON_TERMS = {
    "optiv", "torii", "ironclad", "onetrust", "cadence", "oracle", "navigate",
    "click", "select", "choose", "enter", "assign", "open", "email", "cloud",
    "saas", "response", "operator", "trigger", "condition", "action", "task",
    "control", "risk", "rule", "vendor", "tier", "category", "workflow",
    "contains", "template", "questionnaire", "assessment", "stage", "name",
    "confidential", "appendix", "section", "launching", "review", "reject", "greater",
    # --- ADD THESE TERMS TO STOP FALSE POSITIVES ---
    "ned", "completes", "rcsa", "limit", "miss", "loss", "engineer",
    "ii", "leaver", "account", "critical", "high", "iam", "uplift",
    "pending", "contract", "negative", "rate", "mumbai", "office",
    "unsupported", "components", "actionability", "legacy", "platform",
    "above", "threshold", "reconciliation", "process", "impact",
    "tolerance", "sent", "offshore", "customer", "redress", "custo",
    "meridian", "staffing", "northwind", "analytics", "veritrace", "halloran"
}

MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|"
    "november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)
MONTH_RE = re.compile(r"\b(" + MONTHS + r")\b", re.IGNORECASE)
NUMERIC_DATE_RE = re.compile(r"\b((19|20)\d{2}[/.\-](0[1-9]|1[0-2])[/.\-](0[1-9]|[12]\d|3[01])|"
    r"(0[1-9]|[12]\d|3[01])[/.\-](0[1-9]|1[0-2])[/.\-](19|20)\d{2})\b")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
SECTION_WORD_RE = re.compile(
    r"(appendix|section|figure|table|step|scenario|part|annex|question)\s*$",
    re.IGNORECASE,
)
INITIAL_NAME_RE = re.compile(r"^[A-Z]\.\s?[A-Z]")


def looks_like_real_date(entity_text):
    """Keep DATE_TIME only for calendar dates (month names, 12/05/1990, 2026-01-04, ...).
    Durations such as '14 Days', 'one year', 'Tier 1' or 'quarterly' are not PII."""
    if MONTH_RE.search(entity_text) or NUMERIC_DATE_RE.search(entity_text):
        return True
    return bool(YEAR_RE.search(entity_text) and len(entity_text.split()) > 1)

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



EMAIL_LOCAL_RE = re.compile(r"\b([A-Za-z])\.?([A-Za-z][A-Za-z'\-]+)@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
NAME_PAIR_RE = re.compile(r"\b([A-Z][\w'-]+)[ \t]+([A-Z][\w'-]+)\b")


def names_from_emails(text, hint_text=None):
    """Directory-style documents list 'p.raghunathan@corp.com' next to
    'Priyanka Raghunathan'. Use the emails as a hint to find full names that the
    NER model misses."""
    keys = {}
    for m in EMAIL_LOCAL_RE.finditer(hint_text if hint_text is not None else text):
        initial, surname = m.group(1).lower(), m.group(2).lower().replace("-", "")
        keys[surname] = initial
    results = []
    if not keys:
        return results
    for m in NAME_PAIR_RE.finditer(text):
        first, last = m.group(1), m.group(2)
        initial = keys.get(last.lower().replace("-", ""))
        if initial and first.lower().startswith(initial):
            results.append(RecognizerResult("PERSON", m.start(), m.end(), 0.95))
    return results


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

        # Spans that run across a line break swallow headings / neighbouring lines
        if res.entity_type in ("PERSON", "LOCATION") and "\n" in text[res.start : res.end].strip():
            continue

        if res.entity_type == "LOCATION":
            if any(tok in NON_PERSON_TERMS for tok in re.findall(r"[A-Za-z']+", entity_lower)):
                continue

        if res.entity_type == "PERSON":
            tokens = re.findall(r"[A-Za-z']+", entity_lower)
            # identifiers like QRC_CL_1.3 or words that are really UI/product terms
            if "_" in entity_text or any(ch.isdigit() for ch in entity_text) or entity_text.endswith("-"):
                continue
            if any(tok in NON_PERSON_TERMS for tok in tokens):
                continue
            # "Appendix C. The ..." is not a person
            if INITIAL_NAME_RE.match(entity_text) and SECTION_WORD_RE.search(text[max(0, res.start - 20) : res.start]):
                continue

        if res.entity_type == "URL" and re.fullmatch(r"[A-Z]{1,4}\.[A-Z]{1,4}", entity_text):
            continue  # rule IDs such as WR.MP / WR.SV

        if res.entity_type == "LOCATION" and re.search(r"[\"“”]", entity_text):
            continue

        if res.entity_type == "DATE_TIME":
            # 1. Reject policy/incident reference codes (e.g., PBR-2026-003, ACC-2026-018)
            if re.search(r'(?:PBR|ACC|ISS|INC|GRP|RSK|CTL)-\d{4}', entity_text, re.IGNORECASE):
                continue
            # 2. Reject short month-year tokens without a 4-digit year (e.g., Feb-79)
            if re.match(r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/\s]\d{2}$', entity_text, re.IGNORECASE):
                continue
            # 3. Reject frequency words (e.g., 'annual', 'monthly')
            if entity_lower in FREQUENCY_WORDS:
                continue
            # 4. Reject work experience durations or phone-digit artifacts
            if duration_regex.search(entity_text) or phone_digits_regex.match(entity_text):
                continue
            # 5. Reject standalone 4-digit years
            if standalone_year_regex.match(entity_text):
                continue
            # 6. Fallback calendar check
            if not looks_like_real_date(entity_text):
                continue

        # Reject LOCATION tags if they are generic nouns or whitelisted countries
        if res.entity_type == "LOCATION":
            if (
                entity_lower in ["geographies", "global", "world"]
                or entity_lower in COUNTRY_WHITELIST
                or (entity_lower.startswith("the ") and entity_lower[4:] in COUNTRY_WHITELIST)
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


def detect_and_redact(text, hint_text=None, state=None):
    """hint_text: optional full-document text, used to learn names from email
    addresses that appear on other pages/slides."""
    text = normalize_text(text)
    if hint_text is not None:
        hint_text = normalize_text(hint_text)

    supported_entities = [
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "PERSON",
        "LOCATION",
        "IP_ADDRESS",
        "DATE_TIME",
        "URL",
        "US_SSN",
        "IN_PAN",
        "PASSPORT",
        "EMPLOYEE_ID",
        "DIRECTOR_ID",
        "VENDOR_ID"
        "STREET_ADDRESS",
    ]

    results = analyzer.analyze(
        text=text,
        entities=supported_entities,
        language="en",
        score_threshold=0.2,
    )

    results = list(results) + names_from_emails(text, hint_text)

    # Trim stray whitespace/newlines from entity spans so redaction does not
    # swallow the line break that follows a name.
    for r in results:
        while r.start < r.end and text[r.start].isspace():
            r.start += 1
        while r.end > r.start and text[r.end - 1].isspace():
            r.end -= 1

    valid_results = filter_false_positives(results, text)

    # Consistency pass: if a person's name was detected anywhere (earlier pages or
    # this page), redact every other occurrence too - the NER model is
    # inconsistent about the same name in different surroundings.
    if state is None:
        state = {}
    known_people = {
        v for v, ph in state.get("values", {}).items() if ph.startswith("[PERSON_")
    }
    known_people |= {
        text[r.start : r.end].strip()
        for r in valid_results
        if r.entity_type == "PERSON"
    }
    for name in known_people:
        if len(name) < 5 or "\n" in name:
            continue
        for m in re.finditer(r"(?<![\w])" + re.escape(name) + r"(?![\w])", text):
            valid_results.append(RecognizerResult("PERSON", m.start(), m.end(), 0.9))

    clean_results = filter_overlapping_results(valid_results)

    # `state` lets the caller keep placeholders consistent across pages/slides:
    # the same value gets the same placeholder, and numbering never restarts.
    entity_counters = state.setdefault("counters", {})
    value_to_placeholder = state.setdefault("values", {})
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