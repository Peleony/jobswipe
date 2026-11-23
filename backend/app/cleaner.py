import hashlib
import re
import unicodedata
from typing import Literal

from bs4 import BeautifulSoup

from .models import CleanJob, RawJob, SalaryDetails


INDUSTRY_RULES: dict[str, tuple[str, ...]] = {
    "gastro": (
        r"\bkelner\w*\b",
        r"\bkucharz\w*\b",
        r"\bbarist\w*\b",
        r"\bzmywak\w*\b",
        r"\bgastronomi\w*\b",
        r"\bkuchni\w*\b",
        r"\bpizz\w*\b",
    ),
    "magazyn": (
        r"\bmagazynier\w*\b",
        r"\bkompletacj\w*\b",
        r"\bwóz(?:ek|ka|kiem|ku|ki|ków|kami)\s+widłow(?:y|ego|emu|ym|e|ych|ymi)\b",
        r"\blogistyk\w*\b",
    ),
    "transport": (
        r"\bkierowc\w*\b",
        r"\bkurier\w*\b",
        r"\bprzew(?:óz|oz)\w*\b",
        r"\btaxi\b",
        r"\bautobus\w*\b",
        r"\bciężarow\w*\b",
    ),
    "sprzedaz_d2d": (
        r"\bprzedstawiciel\s+handlow\w*\b",
        r"\bakwizytor\w*\b",
        r"\bcall\s+center\b",
        r"\btelemarket\w*\b",
    ),
}

TAG_RULES: dict[str, tuple[str, ...]] = {
    "kat_d": (
        r"\bkat\s*\.?\s*d(?:\s*\+\s*e)?\b",
        r"\bprawo jazdy\s+(?:kat\s*\.?\s*)?d\b",
        r"\bkategoria\s+d\b",
        r"\bautobus\w*\b",
    ),
    "kat_c": (
        r"\bkat\s*\.?\s*c(?:\s*\+\s*e)?\b",
        r"\bprawo jazdy\s+(?:kat\s*\.?\s*)?c\b",
        r"\bkategoria\s+c(?:\s*\+\s*e)?\b",
        r"\bciężarow\w*\b",
    ),
    "udt": (r"\budt\b", r"\buprawnienia\s+na\s+w[oó]zk\w*\b"),
    "sanepid": (
        r"\bsanepid\w*\b",
        r"\bksiążeczk\w*\s+sanepidowsk\w*\b",
        r"\bksiazeczk\w*\s+sanepidowsk\w*\b",
    ),
    "noce_weekendy": (
        r"\b3\s*[- ]?\s*zmian\w*\b",
        r"\btrzy\s+zmian\w*\b",
        r"\bzmian\w*\s+nocn\w*\b",
        r"\bpraca\s+w\s+weekend\w*\b",
        r"\bdyspozycyjno\w*\s+w\s+weekend\w*\b",
    ),
    "prowizja_scam": (
        r"\bwynagrodzeni\w*\s+prowizyjn\w*\b",
        r"\bnieograniczon\w*\s+zarobk\w*\b",
        r"\bwłasn\w*\s+działaln\w*\b",
        r"\bwlasn\w*\s+dzialaln\w*\b",
        r"\bb2b\b",
    ),
    "orzeczenie": (
        r"\borzeczeni\w*\s+o\s+(?:stop(?:ie|ni)\w*\s+)?niepełnosprawnoś\w*\b",
        r"\borzeczeni\w*\s+o\s+(?:stop(?:ie|ni)\w*\s+)?niepelnosprawnosc\w*\b",
        r"\bstop(?:ie|ni)\w*\s+niepełnosprawnoś\w*\b",
        r"\bstop(?:ie|ni)\w*\s+niepelnosprawnosc\w*\b",
    ),
    "zlecenie_student": (
        r"\bumow\w*\s+zlecen\w*\b",
        r"\bzlecen\w*\s+dla\s+student\w*\b",
        r"\bstatus\s+student\w*\b",
    ),
    "bez_doswiadczenia": (
        r"\bbez\s+(?:wymagan\w*\s+)?doświadczen\w*\b",
        r"\bbez\s+(?:wymagan\w*\s+)?doswiadczen\w*\b",
        r"\bnie\s+wymagamy\s+doświadczen\w*\b",
        r"\bnie\s+wymagamy\s+doswiadczen\w*\b",
        r"\bprzyuczym\w*\b",
    ),
}

_AMOUNT = r"(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[,.]\d{1,2})?"
_SALARY_NUMBER = re.compile(rf"(?<!\d){_AMOUNT}(?!\d)")
_AMOUNT_RANGE = rf"{_AMOUNT}(?:\s*(?:-|–|—|do)\s*{_AMOUNT})?"
_PERIOD_SUFFIX = (
    r"(?:\s*/\s*(?:h\b|mies(?:\.(?!\w)|\b)|miesiąc\w*\b|miesiac\w*\b|mc\b)"
    r"|\s+(?:na\s+godzinę|na\s+godzine|za\s+godzinę|za\s+godzine|"
    r"godzinę|godzine|miesięcznie|miesiecznie|monthly|hourly))?"
)
_CURRENCY_SALARY_PATTERNS = (
    re.compile(rf"(?<!\d){_AMOUNT_RANGE}\s*(?:zł|pln)\b{_PERIOD_SUFFIX}", re.I),
    re.compile(rf"\b(?:zł|pln)\s*{_AMOUNT_RANGE}{_PERIOD_SUFFIX}", re.I),
)
_NON_PLN = re.compile(r"\b(?:usd|eur|gbp|uah|czk|sek|nok|chf|dkk)\b|[$€£]", re.I)
_HOURLY = re.compile(r"(?:/\s*h\b|\b(?:na\s+)?godzin(?:ę|e|y|ach)?\b|\bza\s+godzinę\b|\bhourly\b)", re.I)
_MONTHLY = re.compile(r"(?:/\s*(?:mies\.?|miesiąc|miesiac|mc)\b|\b(?:miesięcznie|miesiecznie|monthly)\b)", re.I)
_NON_SALARY_CONTEXT = re.compile(
    r"\b(?:wiek|lat\w*|rok\w*|rocznik\w*|zmian\w*|doświadczen\w*|doswiadczen\w*)\b",
    re.I,
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in normalized
    )
    return " ".join(normalized.split())


def _plain_text(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    for element in soup(["script", "style", "noscript", "template"]):
        element.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())


def _amount(token: str) -> float:
    number = token.replace("\u00a0", "").replace(" ", "")
    if "," in number:
        number = number.replace(".", "").replace(",", ".")
    elif number.count(".") > 1:
        number = number.replace(".", "")
    return float(number)


def _salary_details(label: str) -> SalaryDetails | None:
    matches = _SALARY_NUMBER.findall(label)
    if not 1 <= len(matches) <= 2:
        return None
    amounts = [_amount(match) for match in matches]
    if any(amount < 10 or amount > 100_000 for amount in amounts):
        return None
    if len(amounts) == 2 and amounts[0] > amounts[1]:
        amounts.reverse()

    if _HOURLY.search(label):
        period: Literal["hour", "month"] = "hour"
    elif _MONTHLY.search(label):
        period = "month"
    else:
        # In Polish listings, small ranges are usually hourly; larger ones monthly.
        period = "hour" if max(amounts) <= 250 else "month"

    return SalaryDetails(
        minimum=amounts[0],
        maximum=amounts[1] if len(amounts) > 1 else None,
        period=period,
        display_label=label.strip(),
    )


def _parse_currency_salary(text: str) -> SalaryDetails | None:
    for pattern in _CURRENCY_SALARY_PATTERNS:
        for match in pattern.finditer(text):
            salary = _salary_details(match.group())
            if salary is not None:
                return salary
    return None


def _parse_salary(raw_salary: str | None) -> SalaryDetails | None:
    if not raw_salary or not raw_salary.strip() or _NON_PLN.search(raw_salary):
        return None

    currency_salary = _parse_currency_salary(raw_salary)
    if currency_salary is not None:
        return currency_salary

    if _NON_SALARY_CONTEXT.search(raw_salary) and not (_HOURLY.search(raw_salary) or _MONTHLY.search(raw_salary)):
        return None

    matches = _SALARY_NUMBER.findall(raw_salary)
    if any(1900 <= _amount(match) <= 2100 for match in matches) and not (
        _HOURLY.search(raw_salary) or _MONTHLY.search(raw_salary)
    ):
        return None
    return _salary_details(raw_salary)


def _matches(text: str, rules: tuple[str, ...]) -> bool:
    return any(re.search(rule, text, re.IGNORECASE) is not None for rule in rules)


def clean_job(job: RawJob) -> CleanJob:
    title = _plain_text(job.title)
    company = _plain_text(job.company)
    city = _plain_text(job.city)
    description = _plain_text(job.description)
    classification_text = normalize_text(" ".join((title, description)))

    identity = "\x1f".join(normalize_text(value) for value in (title, company, city))
    job_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    summary = description[:260].rsplit(" ", 1)[0] if len(description) > 260 else description
    if summary and len(summary) < len(description):
        summary += "…"

    industries = [
        industry for industry, rules in INDUSTRY_RULES.items() if _matches(classification_text, rules)
    ]
    salary = _parse_salary(job.salary_raw) or _parse_currency_salary(description)
    tags = [tag for tag, rules in TAG_RULES.items() if _matches(classification_text, rules)]
    if salary is None:
        tags.append("brak_widelek")

    return CleanJob(
        hash=job_hash,
        title=title,
        company=company,
        city=city,
        url=job.url.strip(),
        description=description,
        summary=summary,
        source=job.source,
        industries=industries,
        tags=tags,
        salary=salary,
    )
