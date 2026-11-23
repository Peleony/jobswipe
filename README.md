# JobSwipe

**Mniej szumu. Więcej pracy.** JobSwipe to otwarty agregator ofert dla studentów i osób na osób szukających swojej pierwszej pracy. Aplikacja pomaga w selekcji i wyborze ofert pracy dla osob które nie mają wyspecjalizowanych umiejętności i do tej pory musiały scrollować całe portale mając do dyspozycji jedynie filtr "bez doświadczenia" i ciągle powtarzające się niechciane oferty.

> **Prawdziwe oferty:** ustaw własny `JOOBLE_API_KEY`. Bez klucza aplikacja może pokazywać oznaczone przykłady demo. Aby całkowicie wyłączyć przykłady także bez klucza, ustaw `DEMO_DATA=false`.

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

Zależności backendu można też zainstalować bezpośrednio z `backend/requirements.txt`; główny plik `requirements.txt` odsyła do tej samej listy. W PowerShell na Windows użyj `py -3.11 -m venv .venv` oraz `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`. Tym samym interpreterem uruchom `backend/seed.py` i `-m uvicorn --app-dir backend app.main:app --reload --host 127.0.0.1 --port 8000`.

Aby pobierać prawdziwe oferty, wpisz `JOOBLE_API_KEY` ze swoim kluczem do pliku `.env` w katalogu głównym projektu (obok `docker-compose.yml`). Zarówno API, jak i `seed.py` odczytują ten plik niezależnie od katalogu uruchomienia; `backend/.env` uzupełnia brakujące wartości. Zmienne ustawione już w środowisku procesu mają pierwszeństwo. Nie udostępniaj pliku z kluczem. Po zmianie klucza uruchom API ponownie i kliknij **Odśwież** lub uruchom `seed.py`, jeśli baza zawiera już dane demo.

API automatycznie pobiera oferty do pustej bazy `backend/data/jobswipe.db`; osobne `seed.py` jest przydatne do ręcznego odświeżania. Przy `DEMO_DATA=auto` (domyślnie) lub `DEMO_DATA=true` przykłady są dodawane tylko bez klucza Jooble. `DEMO_DATA=false` zawsze wyklucza przykłady. Gdy demo jest wyłączone, start API, odświeżanie i `seed.py` usuwają wcześniejsze przykłady z bazy, ale nie zmieniają kopii zapisanych wcześniej w przeglądarce.

Każde ręczne odświeżenie pobiera następną, maksymalnie 20-zapytaniową partię Jooble; kolejne kliknięcia **Odśwież** kontynuują zapamiętane strony. JobSwipe ma konserwatywny lokalny limit 90 zapytań na klucz i dzień UTC (konfigurowalny do maksymalnie 100 zgodnie z darmowym limitem Jooble). To licznik tej bazy, nie obejmuje użycia klucza poza JobSwipe. Import nie ponawia automatycznie błędnych żądań; zachowuje działające strony i ponawia tę samą stronę przy kolejnym ręcznym odświeżeniu. HTTP 429 wstrzymuje import do północy UTC. Postęp i licznik są przechowywane w SQLite i przetrwają restart kontenera.

Opcjonalny `DATABASE_PATH` może wskazywać inną bazę. Ścieżki względne, np. `data/moje-oferty.db`, są liczone od katalogu `backend/`, nie od bieżącego katalogu. Jeżeli lokalny `.env` zawiera `DATABASE_PATH=/app/data/jobswipe.db` ze starszego szablonu, usuń ten wpis: ścieżkę kontenerową ustawia sam Docker Compose.

W drugim terminalu:

```sh
cd frontend
npm ci
npm run dev
```

Otwórz adres Vite wypisany w terminalu (domyślnie `http://localhost:5173`). Dev proxy przekazuje `/api` do `http://127.0.0.1:8000`; można go zmienić przez `VITE_API_PROXY`. Opcjonalny `VITE_API_BASE_URL` pozwala ustawić bazę API dla frontendu. Żaden sekret nie jest potrzebny ani udostępniany klientowi.

## Docker Compose

```sh
[ -f .env ] || cp .env.example .env
# Opcjonalnie dodaj do .env swój JOOBLE_API_KEY.
docker compose up -d --build
```

Po pierwszym uruchomieniu oba kontenery startują ponownie razem z Docker Desktop, o ile nie zatrzymasz ich ręcznie.

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

### `POST /api/jobs/search`

Wyszukiwanie tylko do odczytu z tymi samymi filtrami i limitem 50 ofert co `GET /api/jobs`. Interfejs wysyła listę wykluczonych identyfikatorów w JSON zamiast w adresie URL, dzięki czemu długa historia przesunięć nie blokuje pobierania kolejnych partii. Treść żądania nie zawiera CV ani zapisanych kopii ofert.

```sh
curl 'http://127.0.0.1:8000/api/jobs/search' -H 'Content-Type: application/json' \
  -d '{"city":"Warszawa","require_salary":true,"blocked_tags":["kat_d"],"blocked_industries":["transport"],"exclude_hashes":["0123456789abcdef"]}'
```

### `POST /api/jobs/refresh`

Pobiera wyniki ze skonfigurowanych dostawców, czyści i deduplikuje je oraz wykonuje idempotentny upsert. JSON zwraca `fetched` (poprawnie zmapowane wpisy), `inserted`, `updated`, łączną liczbę `total` w bazie oraz bezpieczne komunikaty błędów dostawców. Dla Jooble pole `jooble` zawiera liczbę odebranych wyników, zapytania tej partii i dzienny licznik, status oraz powód zatrzymania. Nieudany dostawca nie kasuje istniejących ofert ani wyników innych źródeł.

## Prywatność i ograniczenia

- Filtry, odrzucone identyfikatory i pełne snapshoty zapisanych ofert są przechowywane lokalnie w wersjonowanych kluczach `jobswipe.*` w `localStorage`. Przy wyszukiwaniu klient przesyła wybrane filtry oraz identyfikatory ofert już zapisanych lub pominiętych, żeby backend nie zwracał ich ponownie.
- Master CV nigdy nie trafia do API. Prompt jest składany lokalnie i kopiowany przez użytkownika; aplikacja nie wywołuje żadnego API AI.
- Fikcyjne oferty demo są materiałem przykładowym, a nie ogłoszeniami. Bez klucza API nie ma automatycznego dostępu do aktualnych ofert.
- Reguły tagów są jawną heurystyką tekstową, a nie oceną prawną ani dowodem oszustwa. `prowizja_scam` oznacza tylko, że opis zawiera sygnały takie jak prowizja, B2B lub własna działalność — sprawdź warunki u źródła.
- Gdy opis wynagrodzenia nie podaje okresu, etykieta `hour` jest heurystycznie przypisywana stawkom do 250 PLN, a `month` wyższym stawkom. Oryginalny tekst pozostaje widoczny; odznacz filtr stawki, jeśli chcesz zobaczyć także oferty bez widełek.
- Manifest jest gotowy do instalacji jako aplikacja webowa, ale projekt **nie zawiera service workera ani obsługi offline**.

## Dostawcy ofert

Interfejs `BaseJobProvider` znajduje się w `backend/app/providers/base.py`: asynchroniczne `fetch_jobs()` zwraca rekordy `RawJob`. `JoobleProvider` działa po ustawieniu `JOOBLE_API_KEY` w środowisku serwera. `MockPLProvider` jest dostępny tylko bez klucza i tylko gdy demo nie jest wyłączone. Import Jooble rotuje stronami szerokiego zapytania `praca` dla Krakowa, Warszawy, Wrocławia i całej Polski. Lokalizacje, słowa kluczowe, limit na partię oraz lokalny budżet dzienny można zmienić przez `JOOBLE_LOCATIONS`, `JOOBLE_KEYWORDS`, `JOOBLE_REQUESTS_PER_REFRESH` i `JOOBLE_DAILY_REQUEST_LIMIT`. Domyślna partia wysyła maksymalnie 20 zapytań (do 400 wyników przed walidacją i deduplikacją); kolejne ręczne odświeżenia kontynuują zapisane strony zamiast wracać za każdym razem do pierwszej.

Oficjalna dokumentacja podaje darmowy limit 100 zapytań dziennie na klucz dla danego kraju, resetowany o północy UTC; JobSwipe domyślnie zatrzymuje się przy 90, pozostawiając bufor dla innych użyć klucza. Odpowiedź HTTP 429 wstrzymuje import do resetu. Pozostały limit raportowany przez aplikację dotyczy wyłącznie lokalnej bazy i może nie uwzględniać innych aplikacji używających tego samego klucza.

Adapter domyślnie wysyła zapytania do polskiego endpointu `POST https://pl.jooble.org/api/{api_Key}` zgodnie z formatem żądania opisanym w dokumentacji REST Jooble. Jeśli w starszym `.env` masz ustawione `JOOBLE_API_BASE_URL=https://jooble.org/api`, usuń ten wpis lub zmień adres na `https://pl.jooble.org/api`. Zmienna nadal pozwala wskazać inny adres podany przez Jooble dla danego klucza. Testy integracji korzystają z `httpx.MockTransport`, bez prawdziwego klucza.

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
