from urllib.parse import quote_plus

from ..models import RawJob
from .base import BaseJobProvider


class MockPLProvider(BaseJobProvider):
    name = "demo"

    async def fetch_jobs(self) -> list[RawJob]:
        records = [
            ("Pomoc kuchenna na popołudnia", "Przykładowa Bistro", "Kraków", "28–32 zł/h", "Wsparcie kucharza, przygotowanie składników i dbanie o porządek. Grafik do uzgodnienia; mile widziany status studenta."),
            ("Barista / baristka — weekendy", "Fikcyjna Kawiarnia", "Warszawa", "30,50 zł/h", "Przygotowanie kaw i obsługa gości. Szkolenie na miejscu, doświadczenie nie jest wymagane. Praca w weekendy."),
            ("Kelnerka lub kelner", "Demo Restauracja", "Wrocław", "32 zł/h", "Obsługa sali, przyjmowanie zamówień i współpraca z kuchnią. Wymagana książeczka sanepidowska."),
            ("Zmywak — elastyczny grafik", "Przykładowa Bistro", "Kraków", "29 zł/h", "Pomoc na zmywaku w małym zespole. Możliwość dopasowania zmian do zajęć na uczelni."),
            ("Pracownik magazynu — kompletacja", "Demo Logistyka", "Warszawa", "4 800–5 400 zł/mies.", "Kompletowanie zamówień i przygotowanie wysyłek. Praca w systemie 3-zmianowym, wdrożenie od pierwszego dnia."),
            ("Operator wózka widłowego UDT", "Fikcyjny Magazyn", "Wrocław", "5 200 zł/mies.", "Transport palet i przyjęcia towaru. Wymagane aktualne uprawnienia UDT."),
            ("Młodszy pracownik magazynu", "Przykładowe Centrum", "Kraków", "4 500 zł/mies.", "Proste prace magazynowe i pakowanie. Bez doświadczenia; umowa zlecenie dla studentów."),
            ("Kurier / kurierka rowerowa", "Demo Dostawy", "Warszawa", "27–34 zł/h", "Dostawy na terenie centrum, własny rower mile widziany. Elastyczne godziny i rozliczenie godzinowe."),
            ("Kierowca autobusu — linie miejskie", "Fikcyjny Przewoźnik", "Wrocław", "6 800–7 600 zł/mies.", "Przewóz pasażerów na trasach miejskich. Wymagane prawo jazdy kat. D i badania."),
            ("Kierowca ciężarówki C+E", "Przykładowy Transport", "Kraków", "8 000–10 000 zł/mies.", "Przewóz ładunków między oddziałami. Wymagana kategoria C+E i doświadczenie w prowadzeniu ciężarówki."),
            ("Promotor marki — praca z ludźmi", "Demo Promocje", "Warszawa", "32 zł/h", "Rozmowy z klientami w punkcie promocyjnym. Stała stawka godzinowa, umowa zlecenie."),
            ("Przedstawiciel handlowy — teren", "Fikcyjna Sprzedaż", "Kraków", None, "Wynagrodzenie prowizyjne, nieograniczone zarobki. Wymagana własna działalność gospodarcza B2B."),
            ("Ankieter telefoniczny", "Demo Kontakt", "Wrocław", "29 zł/h", "Telefoniczne badania opinii, bez sprzedaży. Płatne szkolenie i elastyczne zmiany."),
            ("Pracownik gastronomii — pizza", "Przykładowa Pizzeria", "Warszawa", "31 zł/h", "Przygotowanie pizzy i obsługa stanowiska. Książeczka sanepidowska będzie potrzebna przed rozpoczęciem pracy."),
            ("Pomoc w sklepie — umowa zlecenie", "Fikcyjny Sklep", "Kraków", "4 700 zł/mies.", "Wykładanie towaru, porządek i wsparcie klientów. Oferta dla studentów, status studenta mile widziany."),
            ("Pracownik produkcji — nocna zmiana", "Demo Produkcja", "Wrocław", "5 100–5 800 zł/mies.", "Pakowanie produktów i kontrola jakości. Zmiany nocne oraz praca w weekendy."),
            ("Asystent biura — praca dla studenta", "Przykładowe Biuro", "Kraków", "30 zł/h", "Wprowadzanie danych i pomoc administracyjna. Bez doświadczenia, elastyczny grafik. Oferta wymaga orzeczenia o niepełnosprawności."),
            ("Pracownik obsługi klienta", "Demo Wsparcie", "Warszawa", "5 000 zł/mies.", "Pomoc klientom przez telefon i e-mail. Szkolenie oraz jasno opisany zakres obowiązków."),
            ("Pomoc kuchenna na popołudnia", "Przykładowa Bistro", "Kraków", "28–32 zł/h", "Wsparcie kucharza, przygotowanie składników i dbanie o porządek. Grafik do uzgodnienia; mile widziany status studenta."),
        ]
        jobs: list[RawJob] = []
        for title, company, city, salary, description in records:
            query = quote_plus(f"{title} {city} praca")
            jobs.append(
                RawJob(
                    title=title,
                    company=company,
                    city=city,
                    url=f"https://www.google.com/search?q={query}",
                    description=description,
                    source="Demo — dane fikcyjne",
                    salary_raw=salary,
                )
            )
        return jobs
