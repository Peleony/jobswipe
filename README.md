# JobSwipe

**Mniej szumu. Więcej pracy.** JobSwipe to otwarty agregator ofert dla studentów i osób na początku kariery. Oferty odkrywa się gestem, a filtry, zapisane ogłoszenia, historia pominięć i Master CV pozostają w przeglądarce — bez konta, analityki, synchronizacji ani połączeń z modelami AI.

> **Ważne: dane demo.** Po pierwszym uruchomieniu aplikacja lokalnie zasiewa bazę fikcyjnymi przykładami ofert. Są wyraźnie oznaczone jako „DEMO · DANE FIKCYJNE” i prowadzą do wyszukiwania, a nie do zmyślonych ogłoszeń. Prawdziwe oferty z Jooble są opcjonalne i wymagają własnego klucza API.

## Wymagania

- Python 3.11 lub nowszy
- Node.js 22+ i npm
- Docker Compose (opcjonalnie, do uruchomienia kontenerowego)

## Uruchomienie lokalne

W katalogu głównym repozytorium:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python backend/seed.py
.venv/bin/uvicorn --app-dir backend app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend-only dependencies can alternatively be installed with `.venv/bin/python -m pip install -r backend/requirements.txt`; the root requirements file includes this same pinned list.

Pierwsze uruchomienie API samo zasieje przykładowe oferty w `backend/data/jobswipe.db`; osobne `seed.py` jest przydatne do ręcznego odświeżania. Ścieżka domyślna jest wyliczana względem aplikacji, nie bieżącego katalogu. Ustaw `DATABASE_PATH`, aby wskazać inną bazę.

W drugim terminalu:

```sh
cd frontend
npm ci
npm run dev
```

Otwórz adres Vite wypisany w terminalu (domyślnie `http://localhost:5173`). Dev proxy przekazuje `/api` do `http://127.0.0.1:8000`; można go zmienić przez `VITE_API_PROXY`. Opcjonalny `VITE_API_BASE_URL` pozwala ustawić bazę API dla frontendu. Żaden sekret nie jest potrzebny ani udostępniany klientowi.

## Docker Compose

```sh
cp .env.example .env
# Opcjonalnie dodaj do .env swój JOOBLE_API_KEY.
docker compose up --build
```

Frontend jest dostępny pod `http://localhost:8080`, API pod `http://localhost:8000`. Nginx serwuje SPA i proxy `/api` do backendu. SQLite jest przechowywany w nazwanym wolumenie `jobswipe_data`; odtworzenie kontenerów go nie usuwa. Klucz Jooble jest przekazywany wyłącznie do kontenera backendu. `.env` i lokalne bazy są ignorowane przez git.

## Testy i build

```sh
.venv/bin/python -m pytest backend/tests
cd frontend
npm test
npm run build
```

Testy backendu obejmują reguły czyszczenia, wynagrodzenia, normalizację i deduplikację, filtry API, idempotentne odświeżanie oraz mockowaną integrację Jooble. Testy frontendu sprawdzają instrukcje ATS w promptach, bezpieczne linki i odporność lokalnego storage. Build nie uruchamia testów przeglądarkowych.

## API

### `GET /api/jobs`

Parametry: `city`, `require_salary`, wielokrotne `blocked_tags[]`, `blocked_industries[]` i `exclude_hashes[]`. Miasto dopasowuje się bez rozróżniania wielkości liter, z polskimi znakami, po fragmencie nazwy. Oferta znika, jeśli zawiera choć jeden z blokowanych tagów lub branż. Odpowiedź zawiera najwyżej 50 ofert.

```sh
curl 'http://127.0.0.1:8000/api/jobs?city=Warszawa&require_salary=true&blocked_tags%5B%5D=kat_d&blocked_tags%5B%5D=prowizja_scam&blocked_industries%5B%5D=transport&exclude_hashes%5B%5D=0123456789abcdef'
```

### `POST /api/jobs/refresh`

Pobiera wyniki ze skonfigurowanych dostawców, czyści i deduplikuje je oraz wykonuje idempotentny upsert. JSON zwraca liczbę pobranych, dodanych i zaktualizowanych rekordów oraz bezpieczne komunikaty błędów dostawców. Nieudany dostawca nie kasuje istniejących ofert ani wyników innych źródeł.

## Prywatność i ograniczenia

- Filtry, odrzucone identyfikatory i pełne snapshoty zapisanych ofert są przechowywane lokalnie w wersjonowanych kluczach `jobswipe.*` w `localStorage`. Przy wyszukiwaniu klient przesyła wybrane filtry oraz identyfikatory ofert już zapisanych lub pominiętych, żeby backend nie zwracał ich ponownie.
- Master CV nigdy nie trafia do API. Prompt jest składany lokalnie i kopiowany przez użytkownika; aplikacja nie wywołuje żadnego API AI.
- Fikcyjne oferty demo są materiałem przykładowym, a nie ogłoszeniami. Bez klucza API nie ma automatycznego dostępu do aktualnych ofert.
- Reguły tagów są jawną heurystyką tekstową, a nie oceną prawną ani dowodem oszustwa. `prowizja_scam` oznacza tylko, że opis zawiera sygnały takie jak prowizja, B2B lub własna działalność — sprawdź warunki u źródła.
- Gdy opis wynagrodzenia nie podaje okresu, etykieta `hour` jest heurystycznie przypisywana stawkom do 250 PLN, a `month` wyższym stawkom. Oryginalny tekst pozostaje widoczny; odznacz filtr stawki, jeśli chcesz zobaczyć także oferty bez widełek.
- Manifest jest gotowy do instalacji jako aplikacja webowa, ale projekt **nie zawiera service workera ani obsługi offline**.

## Dostawcy ofert

Interfejs `BaseJobProvider` znajduje się w `backend/app/providers/base.py`: asynchroniczne `fetch_jobs()` zwraca rekordy `RawJob`. `MockPLProvider` działa zawsze; `JoobleProvider` jest dodawany wyłącznie po ustawieniu `JOOBLE_API_KEY` w środowisku serwera. Dostawca Jooble wysyła zapytania POST dla Krakowa, Warszawy i Wrocławia, mapuje oficjalne pola odpowiedzi na `RawJob` i nie umieszcza klucza w odpowiedziach błędów API JobSwipe.

Jooble dokumentuje ścieżkę `POST https://jooble.org/api/{api_Key}` wraz z parametrami JSON i polami odpowiedzi. Adapter domyślnie używa dokładnie tego endpointu; `JOOBLE_API_BASE_URL` pozwala go nadpisać, jeśli Jooble poda inny adres dla otrzymanego klucza. Integracja jest pokryta testami z `httpx.MockTransport`, ale nie została sprawdzona z prawdziwym kluczem.

- [Oficjalna dokumentacja REST API Jooble](https://help.jooble.org/en/support/solutions/articles/60001448238-rest-api-documentation)
- [Oficjalny przewodnik podłączenia REST API Jooble](https://help.jooble.org/en/support/solutions/articles/60000922689-how-to-connect-to-the-jooble-rest-api)

## Struktura

```text
backend/app/       FastAPI, modele, cleaner, SQLite i dostawcy ofert
backend/seed.py    ręczne odświeżenie bazy
backend/tests/     testy parsera i API
frontend/src/      React, deck, filtry, zapisane oferty, prywatny stan i prompt
frontend/public/   manifest PWA-ready oraz ikony SVG i PNG (192/512)
docker-compose.yml lokalny stack z trwałym wolumenem SQLite
```

Projekt jest udostępniony na licencji MIT. Zasady wkładu opisuje [CONTRIBUTING.md](CONTRIBUTING.md).
