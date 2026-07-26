# SST Dashboard v6

Платформа мониторинга гидрометеостанций Дальнего Востока и Арктики: живые показания станций, ИИ-прогноз (Prophet + GFS + опциональный TimeGPT), календарь/график дежурств, заявки на обслуживание, Telegram-бот — поверх PostgreSQL. Внутри того же FastAPI-приложения живёт картографический слой: рендер прогностических полей **NCEP GFS 0.25°** по Северной Пацифике в PNG-тайлы (проекция Меркатора) поверх OpenLayers-карты.

> Климатические карты ТПО по ERA5 (секции s1–s7, `precompute.py` → `data/*.npz`) удалены: карты рисуются только из GFS GRIB2.

---

## Что внутри

- **Станции** — карта, живые показания (SST, ветер, волна, давление), история за 24 ч
- **ИИ-прогноз** («Serendipity») — Prophet-модель по станции + коррекция по GFS-узлу, с опциональным оверрайдом от Nixtla TimeGPT (квота 50 вызовов/мес, кэш 7 дней)
- **Мониторинг агентов** — лента событий, дашборд сводки, синтетические digest/anomaly-действия
- **Заявки** — создание, назначение, согласование (sign-off) с ролями
- **Календарь** — события, задачи, личные focus-blocks
- **График дежурств** — назначения персонала по станциям, "сегодня"/"ближайшие"
- **Проверки оборудования** — журнал по станциям
- **Telegram-бот** — `/status`, `/station`, `/forecast`, `/pending`, `/summary`, `/events`, свободный текст через GigaChat/Gemini
- **Вебхуки** — приём insight/status/anomaly от внешних агентов (`X-Agent-Key`)
- **Карты GFS** — 6 параметров (темп. поверхности, темп. воздуха 2 м, давление на ур. моря, скорость ветра 10 м, облачность, PWAT) × 6 горизонтов прогноза (+0…+120 ч), рендер на лету из локальных GRIB2 (`cfgrib`), проекция Меркатора, изолинии и подписи
- **Анимация ветра** — частицы по полю u/v 10 м поверх карты

---

## Архитектура

```
                         ┌─────────────────────────┐
                         │   PostgreSQL (docker)   │
                         │ users/stations/readings │
                         │ requests/calendar/...   │
                         └───────────┬─────────────┘
                                     │ asyncpg
┌───────────────┐  GRIB2 0.25°  ┌────▼──────────────────────┐
│ локальные GFS │ ─────────────▶│       app.py (FastAPI)     │
│ *.grb2 (00Z)  │   (cfgrib)    │  • lifespan: init_db,      │
│ GFS_LOCAL_PATH│               │    start_scheduler         │
└───────────────┘               │  • роуты карт GFS —        │
                                 │    прямо в app.py          │
                                 │  • include_router(...) —   │
                                 │    11 роутеров из routers/ │
                               └──────────┬────────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
             services/scheduler   services/prophet_forecast  services/telegram_bot
             (почасовой опрос      (SST-прогноз по станции)   (long polling +
              Open-Meteo)                                       webhook)
                    │
             services/gigachat (Gemini → GigaChat fallback, брендируется как «GigaChat»)
                                          │
                                   static/ (SPA, vanilla JS)
                                   OpenLayers + Chart.js
```

**Запуск**: сервер поднимается без БД и без Prophet/GEE (роутеры и планировщик просто не грузятся, в логах — warning). Карты GFS работают независимо от Postgres, читая GRIB2 из `GFS_LOCAL_PATH`.

---

## Технологический стек

### Backend
| Компонент | Роль |
|---|---|
| **FastAPI** | REST API, статика, 11 роутеров + inline GFS-эндпоинты |
| **asyncpg** | пул соединений к PostgreSQL (Neon в проде / локальный docker в деве) |
| **python-jose + passlib[bcrypt]** | JWT-аутентификация (access/refresh), хеши паролей |
| **APScheduler-подобный фон** (`services/scheduler.py`, чистый `asyncio`) | почасовой сбор данных, поллинг Telegram, синтетическая активность |
| **Prophet** | базовый прогноз ТПО по станции |
| **Nixtla TimeGPT** (`services/serendipity.py`) | опциональный оверрайд прогноза + коррекция смещения GFS |
| **Google Earth Engine** (`ee`, `services/gee_gfs.py`) | извлечение GFS-узла по координатам станции |
| **cfgrib** | чтение локальных GRIB2-файлов GFS |
| **NumPy / SciPy / Pillow / pyproj / shapely / matplotlib** | рендер PNG-карт GFS (Меркатор, LUT, размытие, изолинии) и береговой линии |
| **httpx** | запросы к Open-Meteo, Telegram Bot API, GigaChat/Gemini |

### Frontend
| Компонент | Роль |
|---|---|
| **OpenLayers** | карта станций, карты GFS (ImageStatic слой) |
| **Chart.js** | графики прогнозов, аналитика, мониторинг |
| **Vanilla JS** (11 модулей в `static/`) | вся логика без сборщика/фреймворка |

### Данные
- **GFS GRIB2 0.25°** — локальные файлы прогона 00Z, читаются `cfgrib`; путь задаётся `GFS_LOCAL_PATH`, шаблон `<base>/<YYYY>/<MM>/<DD>/00/gfs.t00z.pgrb2.0p25.f{fhh}.grb2`, домен подрезается до 26–72°N / 117–246°E
- **Natural Earth 1:10m land** — `data/ne_10m_land.geojson` для береговой линии (скачивается `precompute_coastline.py`)
- **PostgreSQL** — 13 таблиц (см. ниже), заполняются `migrate.py` + `seed.py`

---

## Схема БД (`migrate.py`)

| Таблица | Назначение |
|---|---|
| `users` | учётки, роли (`supervisor`/`data_analyst`/`observer`/`engineer`), пароль-хеш |
| `stations` | справочник станций (код, координаты, регион, статус) |
| `readings` | почасовые показания (SST, ветер, волна, давление, видимость...) |
| `gfs_forecasts` | прогнозы GFS по станции/часу + скорректированные значения |
| `personnel` | привязка персонала к станциям |
| `assignments` | график дежурств |
| `requests` | заявки на обслуживание + согласование |
| `equipment_checks` | журнал проверок оборудования |
| `calendar_events` | события календаря |
| `agent_activity` | лента событий/действий агентов |
| `notifications` | лог отправленных уведомлений (Telegram и др.) |
| `tasks` | задачи в календаре |
| `focus_blocks` | личные блоки фокус-времени |

Заполнение демо-данными (`seed.py`): 20 станций ДВ/Арктики, 15 пользователей, 30 дней почасовых показаний, прогнозы, события, заявки, назначения.

---

## API

### Аутентификация (`auth.py`, без префикса)
| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/auth/login` | логин, выдаёт access + refresh JWT |
| POST | `/api/auth/refresh` | обновление access-токена |
| GET | `/api/auth/me` | текущий пользователь |

### Станции — `/api/monitoring` (`routers/stations.py`)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/stations` | список станций + последнее показание |
| GET | `/stations/{id}` | детали станции + показания за 24 ч |
| GET | `/stations/{id}/readings` | показания за N часов |
| GET | `/readings/latest` | последнее показание по каждой станции |
| POST | `/readings` | добавить показание (роль observer/supervisor) |

### Прогноз — `/api/monitoring/forecast` (`routers/forecast.py`)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/stations/{id}/forecast` | Prophet + GFS-узел + опциональный TimeGPT |
| GET | `/stations/{id}/forecast/history` | прогнозы прошлых периодов против факта |

### Мониторинг — `/api/monitoring` (`routers/monitoring.py`)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/feed` | лента активности (пагинация) |
| GET | `/dashboard/summary` | сводка: статусы станций, заявки, аномалии, графики |
| POST | `/actions/{action}` | запустить digest/anomaly-check (роль supervisor) |

### Заявки — `/api/monitoring/requests` (`routers/requests.py`)
| Метод | Путь | Описание |
|---|---|---|
| GET / POST | `/` | список / создание заявки |
| PUT | `/{id}` | обновление |
| POST | `/{id}/sign` | согласование (роль supervisor) |

### Календарь — `/api/monitoring/calendar` (`routers/calendar_routes.py`)
| Метод | Путь | Описание |
|---|---|---|
| GET / POST | `/events` | события |
| PUT / DELETE | `/events/{id}` | обновление / удаление (роль supervisor) |
| GET / POST | `/tasks` | задачи |
| PUT | `/tasks/{id}` | обновление задачи |
| GET / POST | `/focus-blocks` | личные focus-blocks |

### Оборудование — `/api/monitoring/equipment` (`routers/equipment.py`)
| Метод | Путь | Описание |
|---|---|---|
| GET / POST | `/checks` | список / добавление проверки (роль engineer/supervisor) |

### Пользователи — `/api/monitoring/users` (`routers/users.py`)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/` | список пользователей (роль supervisor) |
| GET | `/personnel` | персонал + станции |
| POST | `/assignments` | назначение (роль supervisor) |

### Регионы — `/api/regions` (`routers/regions.py`)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/` | регионы + агрегаты статусов станций |
| GET | `/geojson` | сырой GeoJSON |
| GET | `/{code}` | детали региона |

### График дежурств — `/api/monitoring/schedule` (`routers/schedule.py`)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/`, `/stations`, `/personnel` | списки для UI |
| POST / PUT / DELETE | `/`, `/{id}` | CRUD назначений (роль supervisor) |
| GET | `/today`, `/upcoming` | текущие / ближайшие дежурства |

### Вебхуки — `/api/webhooks` (`routers/webhooks.py`)
| Метод | Путь | Описание |
|---|---|---|
| POST | `/agent/insight`, `/agent/status`, `/agent/anomaly` | приём от внешних агентов (`X-Agent-Key`) |
| POST | `/telegram` | вебхук Telegram-бота |

### Карты GFS — inline в `app.py` (без префикса)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/gfs/meta` | прогон 00Z, доступные горизонты, список параметров, mercator_extent |
| GET | `/api/gfs/map/{param}/{fhour_idx}.png` | PNG-карта параметра (Меркатор) |
| GET | `/api/gfs/colorscale/{param}` | LUT + тики цветовой шкалы (`fhour_idx`, `percentile`) |
| GET | `/api/gfs/wind/{fhour_idx}` | поле u/v 10 м (JSON) для анимации частиц |
| GET | `/api/coastline.svg`, `/api/coastline.geojson` | береговая линия |

Параметры запроса карты: `percentile` (99 / 99.9 / 100), `scale` (1–3), `blur`, `contours`, `contour_labels`.

---

## Параметры карт GFS

Единый реестр — `GFS_PARAMS` в `app.py` (GRIB2-селекторы + единицы + палитра + подпись).

| ID | Название | GRIB2 | Единицы | Палитра |
|---|---|---|---|---|
| `gfs_t` | Темп. поверхности | `t` / surface | °C | RdYlBu_r |
| `gfs_2t` | Темп. воздуха 2 м | `2t` / heightAboveGround | °C | RdYlBu_r |
| `gfs_prmsl` | Давление на ур. моря | `prmsl` / meanSea | гПа | Blues |
| `gfs_wind` | Скорость ветра 10 м | `10u` + `10v` → √(u²+v²) | м/с | Plasma |
| `gfs_tcc` | Облачность | `tcc` / atmosphere | % | Greys |
| `gfs_pwat` | Запас воды (PWAT) | `pwat` / atmosphereSingleLayer | кг/м² | Greens |

Горизонты (`GFS_FHOURS`): +0, +24, +48, +72, +96, +120 ч — по ним строится сетка сравнения из 6 карт.

---

## Быстрый старт

```bash
# 1. Postgres + n8n локально
docker compose up -d

# 2. Зависимости — requirements.txt неполный (см. ниже), проще:
pip install fastapi "uvicorn[standard]" asyncpg python-jose "passlib[bcrypt]" \
            python-dotenv httpx pandas prophet earthengine-api shapely \
            numpy scipy Pillow pyproj matplotlib cfgrib python-multipart smbprotocol

# 3. .env (см. таблицу ниже)
cp .env.example .env   # создать вручную по образцу ниже

# 4. Схема БД + демо-данные
python migrate.py
python seed.py

# 5. Береговая линия для карт (скачивает data/ne_10m_land.geojson)
python precompute_coastline.py

# 6. Запуск
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

Роутеры, для которых не хватает зависимостей или переменных окружения, **не крашат** приложение — `_try_include()` в `app.py` перехватывает исключение и просто логирует warning. То же для планировщика и БД в `lifespan()`.

### Переменные окружения (`.env`)

| Переменная | Обязательна | Назначение |
|---|---|---|
| `DATABASE_URL` / `LOCAL_DB_URL` | да (для всего кроме карт GFS) | строка подключения Postgres |
| `GFS_LOCAL_PATH` | нет | корень локального архива GRIB2 GFS (по умолчанию `/mnt/meteo/data/NOAA/NCEP/FTPPRD/pub/data/nccf/com/gfs/prod0p25.sfc`) |
| `NEON_DATABASE_URL` | нет | прод-БД (Neon) |
| `JWT_SECRET` | да (для auth) | подпись JWT |
| `TELEGRAM_BOT_TOKEN` | нет | Telegram-бот |
| `AGENT_API_KEY` | нет | ключ для `/api/webhooks/agent/*` |
| `GEE_PROJECT_ID` | нет | Google Earth Engine проект |
| `GEMINI_API_KEY` | нет | основной backend для «GigaChat»-ответов |
| `GIGACHAT_CLIENT_ID/SECRET` | нет | fallback-backend |
| `GFS_SMB_*` | нет | используется только мёртвым `services/smb_gfs.py` (см. «Технический долг») |

---

## Технический долг

- **`requirements.txt` неполный** — не содержит `asyncpg`, `python-jose`, `passlib`, `python-dotenv`, `httpx`, `pandas`, `prophet`, `earthengine-api`, `pytest`. Реально используемые пакеты — см. список выше.
- **`routers/gfs_forecast.py`** — не подключён в `app.py` (нет в `_try_include`), дублирует логику, которая живёт inline в `app.py`. Мёртвый код.
- **`services/smb_gfs.py`** и **`services/gfs_simulator.py`** — нигде не импортируются, недостижимы.
- **`data/*.npz`** (`meta`, `sst_raw`, `s2`, `s3`, `s5`, `s6`, `s7`) и **`data/ocean_mask.npy`** — остатки удалённого ERA5-слоя, кодом больше не читаются, можно удалить (~101 МБ).
- **`data/regions.geojson`** отсутствует в репозитории — `/api/regions` не найдёт файл, пока его не добавить вручную.
- **`render.yaml`** не поднимает Postgres и планировщик — деплой рассчитан только на слой карт.

---

## Структура файлов

```
sst_dashboard_v6/
├── app.py                  # FastAPI: lifespan, роутеры, inline GFS API, статика
├── auth.py                 # JWT-логин/рефреш/me
├── config.py                # чтение .env
├── db.py                    # asyncpg pool
├── models.py                 # Pydantic-схемы ответов
├── migrate.py                 # DDL — 13 таблиц
├── seed.py                    # демо-данные
├── precompute_coastline.py     # скачивание ne_10m_land.geojson
├── docker-compose.yml           # Postgres + n8n
├── render.yaml                   # деплой
├── routers/
│   ├── stations.py, forecast.py, monitoring.py, requests.py,
│   │   calendar_routes.py, equipment.py, users.py, regions.py,
│   │   schedule.py, webhooks.py        # 10 подключённых роутеров
│   └── gfs_forecast.py                 # НЕ подключён (мёртвый код)
├── services/
│   ├── scheduler.py, data_generator.py, prophet_forecast.py,
│   │   serendipity.py, gee_gfs.py, gigachat.py, notification.py,
│   │   telegram_bot.py                 # активно используются
│   └── smb_gfs.py, gfs_simulator.py    # не используются
├── tests/
│   ├── test_calendar_security.py       # 401 без авторизации
│   └── test_schedule_security.py       # 401 без авторизации + нет утечки phone
├── data/                     # ne_10m_land.geojson + кэш GFS
└── static/
    ├── index.html             # SPA: карты GFS, ИИ-прогноз, мониторинг, календарь, заявки
    ├── app.js, auth.js, analytics.js, cabinet.js, calendar.js,
    │   forecast.js, monitoring.js, regions.js,
    │   requests_ui.js, schedule.js, stations.js
    ├── style.css, monitoring.css
    └── vendor/                # OpenLayers, Chart.js (локально)
```

---

## Тесты

```bash
pytest tests/
```

Оба файла — регрессионные проверки безопасности: `test_calendar_security.py` подтверждает, что `/api/monitoring/calendar/*` требует авторизации; `test_schedule_security.py` — то же для расписания плюс проверка, что ответы не содержат поле `phone` (см. коммит `da9eb6e` — фикс утечки PII).
