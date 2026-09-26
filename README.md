# Cinema Portal (Forkplayer FXML backend)

Flask-бэкенд для Forkplayer: поиск через Kinopoisk API, потоки от HdRezka / Rutracker / Rutube (Filmach) / VK Video, локальные видео, избранное и история просмотров.

---

## Провайдеры

- **HdRezka** (`videobalancers/HdRezkaApi.py`) — поиск, сезоны/эпизоды/переводы, потоки и субтитры.
- **Rutracker** (`videobalancers/RutrackerApi.py`) — поиск раздач, инфо о топике, скачивание `.torrent` (нужны логин/пароль, опционально прокси).
- **Rutube / Filmach** (`videobalancers/FilmachRutube.py`, флаг `ENABLE_RUTUBE`) — потоки через Rutube API.
- **VK Video** (`videobalancers/VkVideoApi.py`, флаг `ENABLE_VKVIDEO`) — потоки через VK Video API.
- **Локальные видео** — сканирование каталогов из `LOCAL_VIDEO_DIRS`, раздача через `/serve_local_video`, magnet через `yt-dlp`.

Выбор провайдеров: `VideoBalancersApi.get_providers()` — HdRezka по факту поиска, остальные по флагам/кредам в `config.py`.

---

## API Endpoints

- `/` — главная FXML-страница.
- `/search` — поиск фильмов/сериалов (Kinopoisk API).
- `/process_item` — выбор провайдера для найденного тайтла.
- `/rezka/process_item/` — навигация HdRezka (сезон/эпизод/перевод).
- `/tracker/process_item` — навигация Rutracker.
- `/filmach/process_item` — навигация Rutube/Filmach.
- `/vkvideo/process_item` — навигация VK Video.
- `/bookmarks/` — избранное.
- `/add_to_fav/`, `/rem_from_fav/` — добавить/убрать избранное.
- `/mark_watched/` — отметить просмотренное.
- `/local_videos/` — список локальных файлов.
- `/serve_local_video` — раздача локального файла.
- `/stream_proxy` — проксирование HTTP-потоков (если `ENABLE_HTTP_PROXY_STREAMS=True`).
- `/res/<res>` — статика (иконки из `res/`).

Авторизация: query-параметры `box_mac` (или запрос с `127.0.0.1`).

---

## Структура

- `server.py` — Flask-приложение, все эндпоинты, состояние, кэш.
- `VideoBalancersApi.py` — поиск Kinopoisk + выбор провайдеров.
- `videobalancers/` — парсеры провайдеров (`HdRezkaApi.py`, `RutrackerApi.py`, `FilmachRutube.py`, `VkVideoApi.py`).
- `utils.py` — `load_json/save_json`, `auth_required`, чистка URL, скан локальных видео.
- `templates/` — FXML-шаблоны (`main_page.json`, `search_result_page.json`).
- `res/` — иконки.
- `config.py` (не в git, см. `config.py.example`) — креды и флаги.
- `db.json` (не в git, см. `db.json.example`) — `{"bookmarks": [], "watched": []}`.
- `app_state.json` (не в git, автогенерация) — кэш соответствия `kp_id -> title`.
- `hls_output/` (не в git) — временные файлы.

---

## Setup

- Python 3.8+, `ffmpeg` в PATH (для локальных/прокси-потоков).
- `pip install -r requirements.txt`
- `cp config.py.example config.py` — заполнить `REZKA_EMAIL/PASSWORD`, `KINOPOISK_API_KEY`, `RUTRACKER_*`, флаги `ENABLE_*`.
- `cp db.json.example db.json` (или создастся при первом использовании).
- `python server.py`

Зависимости (`requirements.txt`): Flask, Flask-CORS, Flask-Caching, requests, beautifulsoup4, lxml, curl_cffi, yt-dlp.
