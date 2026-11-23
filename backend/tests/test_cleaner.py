import pytest

from backend.app.cleaner import clean_job, normalize_text
from backend.app.models import RawJob


def raw_job(title: str = "Pracownik", description: str = "", salary: str | None = None) -> RawJob:
    return RawJob(
        title=title,
        company="Firma Demo",
        city="Kraków",
        url="https://example.org/oferta",
        description=description,
        source="Test",
        salary_raw=salary,
    )


@pytest.mark.parametrize(
    ("text", "industry"),
    [
        ("Kelnerka w kawiarni", "gastro"),
        ("Kucharz zmianowy", "gastro"),
        ("Barista", "gastro"),
        ("Praca na zmywaku", "gastro"),
        ("Pracownik gastronomii", "gastro"),
        ("Pomoc w kuchni", "gastro"),
        ("Pizzaiolo", "gastro"),
        ("Magazynier", "magazyn"),
        ("Kompletacja zamówień", "magazyn"),
        ("Operator wózka widłowego", "magazyn"),
        ("Asystent logistyka", "magazyn"),
        ("Kierowca", "transport"),
        ("Kurier", "transport"),
        ("Przewóz osób", "transport"),
        ("Kierowca taxi", "transport"),
        ("Autobus miejski", "transport"),
        ("Ciężarowy transport krajowy", "transport"),
        ("Przedstawiciel handlowy", "sprzedaz_d2d"),
        ("Akwizytor", "sprzedaz_d2d"),
        ("Konsultant call center", "sprzedaz_d2d"),
        ("Telemarketer", "sprzedaz_d2d"),
    ],
)
def test_industry_rules_include_practical_polish_inflections(text: str, industry: str) -> None:
    assert industry in clean_job(raw_job(title=text)).industries


@pytest.mark.parametrize(
    ("text", "tag"),
    [
        ("Wymagane kat. D", "kat_d"),
        ("Prawo jazdy D i przewóz pasażerów", "kat_d"),
        ("Kierowca autobusu", "kat_d"),
        ("Prawo jazdy kat. C", "kat_c"),
        ("Kategoria C+E", "kat_c"),
        ("Kierowca ciężarowy", "kat_c"),
        ("Wymagamy uprawnień UDT", "udt"),
        ("Wymagane uprawnienia na wózki widłowe", "udt"),
        ("Ważna książeczka sanepidowska", "sanepid"),
        ("Badania do sanepidu", "sanepid"),
        ("Praca w systemie 3-zmianowym", "noce_weekendy"),
        ("Zmiany nocne i praca w weekendy", "noce_weekendy"),
        ("Dyspozycyjność w weekendy", "noce_weekendy"),
        ("Wynagrodzenie prowizyjne", "prowizja_scam"),
        ("Nieograniczone zarobki", "prowizja_scam"),
        ("Wymagana własna działalność gospodarcza", "prowizja_scam"),
        ("Prowadzenie własnej działalności", "prowizja_scam"),
        ("Kontrakt B2B", "prowizja_scam"),
        ("Wymagane orzeczenie o niepełnosprawności", "orzeczenie"),
        ("Wymagane orzeczenia o niepełnosprawności", "orzeczenie"),
        ("Wymagany stopień niepełnosprawności", "orzeczenie"),
        ("Wymagane orzeczenie o stopniu niepełnosprawności", "orzeczenie"),
        ("Umowa zlecenie dla studentów", "zlecenie_student"),
        ("Umowy zlecenia", "zlecenie_student"),
        ("Bez doświadczenia", "bez_doswiadczenia"),
        ("Nie wymagamy doświadczenia", "bez_doswiadczenia"),
        ("Przyuczymy do pracy na miejscu", "bez_doswiadczenia"),
    ],
)
def test_tag_rules_are_case_insensitive_and_cover_polish_wording(text: str, tag: str) -> None:
    assert tag in clean_job(raw_job(description=text)).tags


@pytest.mark.parametrize(
    "text",
    [
        "Prawo jazdy kategorii B",
        "Dostępność od poniedziałku",
        "Kierowca z kategorią B, praca dzienna",
    ],
)
def test_category_does_not_match_category_b_or_letter_inside_a_word(text: str) -> None:
    assert "kat_d" not in clean_job(raw_job(description=text)).tags
    assert "kat_c" not in clean_job(raw_job(description=text)).tags


@pytest.mark.parametrize(
    ("text", "tag"),
    [
        ("Wymagana książeczka do celów bibliotecznych", "sanepid"),
        ("Orzeczenie sądu pracy", "orzeczenie"),
        ("SuperUDTowy system", "udt"),
    ],
)
def test_narrow_tag_rules_reject_unrelated_word_matches(text: str, tag: str) -> None:
    assert tag not in clean_job(raw_job(description=text)).tags


def test_industry_rules_require_word_or_stem_boundaries() -> None:
    assert "gastro" not in clean_job(raw_job(title="Podkuchniak")).industries


@pytest.mark.parametrize(
    ("label", "minimum", "maximum", "period"),
    [
        ("28 - 32 zł", 28, 32, "hour"),
        ("30,50 zł/h", 30.5, None, "hour"),
        ("4 500–5 500 zł/mies.", 4500, 5500, "month"),
        ("5 000 PLN miesięcznie", 5000, None, "month"),
        ("4 500–5 500", 4500, 5500, "month"),
    ],
)
def test_salary_ranges_support_polish_spacing_decimals_and_periods(
    label: str, minimum: float, maximum: float | None, period: str
) -> None:
    salary = clean_job(raw_job(salary=label)).salary
    assert salary is not None
    assert salary.minimum == minimum
    assert salary.maximum == maximum
    assert salary.currency == "PLN"
    assert salary.period == period
    assert salary.display_label == label


@pytest.mark.parametrize("label", [None, "", "brak widełek", "do uzgodnienia"])
def test_unknown_salary_is_not_invented(label: str | None) -> None:
    job = clean_job(raw_job(salary=label))
    assert job.salary is None
    assert "brak_widelek" in job.tags


def test_non_pln_salary_is_not_labeled_as_pln() -> None:
    job = clean_job(raw_job(salary="€1,200–1,500 per month"))
    assert job.salary is None
    assert "brak_widelek" in job.tags


def test_currency_adjacent_description_salary_is_used_when_field_is_unusable() -> None:
    job = clean_job(raw_job(
        salary="wiek 22 lata",
        description="Wynagrodzenie 30,50 zł/h; oferta od 2024, dostępne 3 zmiany.",
    ))
    assert job.salary is not None
    assert job.salary.minimum == 30.5
    assert job.salary.period == "hour"
    assert job.salary.display_label == "30,50 zł/h"
    assert "noce_weekendy" in job.tags
    assert "brak_widelek" not in job.tags


def test_description_without_currency_does_not_turn_age_year_or_shift_into_salary() -> None:
    job = clean_job(raw_job(
        description="Doświadczenie 2022–2024, wiek 22 lata, system 3-zmianowy.",
    ))
    assert job.salary is None
    assert "brak_widelek" in job.tags
    assert "noce_weekendy" in job.tags


@pytest.mark.parametrize("label", ["3 zmiany", "22 lata", "2024"])
def test_explicit_salary_field_rejects_shift_age_and_year_values(label: str) -> None:
    job = clean_job(raw_job(salary=label))
    assert job.salary is None
    assert "brak_widelek" in job.tags


def test_hash_normalizes_unicode_case_whitespace_and_punctuation() -> None:
    first = raw_job(title="  KELNERKA—Kraków  ")
    second = raw_job(title="kelnerka Kraków")
    assert clean_job(first).hash == clean_job(second).hash
    assert normalize_text("  ŁÓDŹ—Praca  ") == "łódź praca"


def test_hash_identity_uses_separators_between_fields() -> None:
    first = raw_job(title="ab")
    first.company = "c"
    first.city = "x"
    second = raw_job(title="a")
    second.company = "bc"
    second.city = "x"
    assert clean_job(first).hash != clean_job(second).hash


def test_description_html_is_safely_stripped_and_summary_is_populated() -> None:
    job = raw_job(description="<p>Pomoc <strong>w kuchni</strong></p><script>złośliwy()</script>")
    cleaned = clean_job(job)
    assert cleaned.description == "Pomoc w kuchni"
    assert "złośliwy" not in cleaned.description
    assert cleaned.summary == "Pomoc w kuchni"
