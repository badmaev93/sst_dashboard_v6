# SST Dashboard v6

Платформа мониторинга гидрометеостанций Дальнего Востока и Арктики: живые показания станций, ИИ-прогноз (Prophet + GFS + опциональный TimeGPT), календарь/график дежурств, заявки на обслуживание, Telegram-бот — поверх PostgreSQL. Внутри того же FastAPI-приложения по-прежнему живёт исходный проект: рендер климатических карт ТПО (ERA5, precompute → PNG) и GFS-оверлей поверх карты.

> Это НЕ простой netCDF-дашборд, как было написано в старом README. Это гибрид: станционный мониторинг на Postgres + унаследованный слой климатических карт.

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
- **Карты ТПО (наследие)** — климатология, OLS-тренд, R², дисперсия, тренд дисперсии, градиент фронтов, аномалии по годам — рендерятся на лету из `.npz`, спроецированы в Меркатор
- **GFS-оверлей** — ветровые поля поверх карты из локальных GRIB-файлов (`cfgrib`)

---

## Архитектура

```
                         ┌─────────────────────────┐
                         │   PostgreSQL (docker)   │
                         │ users/stations/readings │
                         │ requests/calendar/...   │
                         └───────────┬─────────────┘
                                     │ asyncpg
┌───────────────┐   npz-кэш   ┌──────▼──────────────────────┐
│ precompute.py │ ───────────▶│         app.py (FastAPI)     │
│ (запуск вручную,           │  • lifespan: init_db,         │
│  строит data/*.npz)        │    start_scheduler            │
└───────────────┘             │  • роуты карт ТПО/GFS —      │
                               │    прямо в app.py            │
                               │  • include_router(...) —     │
                               │    11 роутеров из routers/   │
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

**Запуск**: сервер поднимается без БД и без Prophet/GEE (роутеры и планировщик просто не грузятся, в логах — warning). Карты ТПО работают независимо от Postgres, читая `data/*.npz`.

---

## Технологический стек

### Backend
| Компонент | Роль |
|---|---|
| **FastAPI** | REST API, статика, 11 роутеров + inline SST/GFS-эндпоинты |
| **asyncpg** | пул соединений к PostgreSQL (Neon в проде / локальный docker в деве) |
| **python-jose + passlib[bcrypt]** | JWT-аутентификация (access/refresh), хеши паролей |
| **APScheduler-подобный фон** (`services/scheduler.py`, чистый `asyncio`) | почасовой сбор данных, поллинг Telegram, синтетическая активность |
| **Prophet** | базовый прогноз ТПО по станции |
| **Nixtla TimeGPT** (`services/serendipity.py`) | опциональный оверрайд прогноза + коррекция смещения GFS |
| **Google Earth Engine** (`ee`, `services/gee_gfs.py`) | извлечение GFS-узла по координатам станции |
| **cfgrib** | чтение локальных GRIB2-файлов GFS для карт ветра |
| **NumPy / SciPy / Pillow / netCDF4 / pyproj** | вычисления и рендер PNG-карт ТПО (Меркатор, LUT, Гауссово размытие) |
| **httpx** | запросы к Open-Meteo, Telegram Bot API, GigaChat/Gemini |

### Frontend
| Компонент | Роль |
|---|---|
| **OpenLayers** | карта станций, карты ТПО/GFS (ImageStatic слой) |
| **Chart.js** | графики прогнозов, аналитика, мониторинг |
| **Vanilla JS** (11 модулей в `static/`) | вся логика без сборщика/фреймворка |

### Данные
- **ERA5 Monthly Averaged SST** — исходный `.nc`, регион 26–72°N 117–246°E, 1979–2026
- **PostgreSQL** — 13 таблиц (см. ниже), заполняются `migrate.py` + `seed.py`
- **GFS GRIB2** — локальные файлы, читаются `cfgrib`

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

### Карты ТПО / GFS — inline в `app.py` (без префикса)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/meta` | метаданные сетки, секции, даты |
| GET | `/api/map/{section}/{season_type}/{season_idx}.png` | PNG-карта (Меркатор) |
| GET | `/api/coastline.svg`, `/api/coastline.geojson` | береговая линия |
| GET | `/api/colorscale/{section}` | тики цветовой шкалы |
| GET | `/api/timeseries`, `/api/field_value` | точечные запросы |
| GET | `/api/point_stats`, `/api/point_series`, `/api/point_annual` | статистика/ряды по клику |
| GET | `/api/anomaly/{year}/{month}` | поле аномалий за месяц |
| GET | `/api/gfs/meta`, `/api/gfs/wind/{fhour_idx}` | метаданные и ветер GFS (из локальных GRIB) |

---

## Секции карт ТПО

| ID | Название | Цветовая шкала | Статус |
|---|---|---|---|
| s1 | Клим. среднее | RdYlBu_r | ⚠️ `data/s1.npz` отсутствует — вернёт 500 |
| s2 | OLS тренд (p<0.05) | RdBu_r симметричный | ✅ |
| s3 | R² | Viridis 0→1 | ✅ |
| s4 | Межгодовая дисперсия | YlOrRd | ⚠️ `data/s4.npz` отсутствует — вернёт 500 |
| s5 | Тренд дисперсии (p<0.05) | RdBu_r симметричный | ✅ |
| s6 | Градиент / фронты | Hot_r | ✅ |
| s7 | Аномалии по годам | RdBu_r ±VM | ✅ |

---

## Быстрый старт

```bash
# 1. Postgres + n8n локально
docker compose up -d

# 2. Зависимости — requirements.txt неполный (см. ниже), проще:
pip install fastapi "uvicorn[standard]" asyncpg python-jose "passlib[bcrypt]" \
            python-dotenv httpx pandas prophet earthengine-api shapely \
            netCDF4 numpy scipy Pillow pyproj cfgrib python-multipart smbprotocol

# 3. .env (см. таблицу ниже)
cp .env.example .env   # создать вручную по образцу ниже

# 4. Схема БД + демо-данные
python migrate.py
python seed.py

# 5. Карты ТПО (опционально, нужны для s1–s7) — требует исходный .nc файл
python precompute.py
python precompute_coastline.py

# 6. Запуск
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

Роутеры, для которых не хватает зависимостей или переменных окружения, **не крашат** приложение — `_try_include()` в `app.py` перехватывает исключение и просто логирует warning. То же для планировщика и БД в `lifespan()`.

### Переменные окружения (`.env`)

| Переменная | Обязательна | Назначение |
|---|---|---|
| `DATABASE_URL` / `LOCAL_DB_URL` | да (для всего кроме карт ТПО) | строка подключения Postgres |
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

- **`requirements.txt` неполный** — не содержит `asyncpg`, `python-jose`, `passlib`, `python-dotenv`, `httpx`, `pandas`, `prophet`, `earthengine-api`, `shapely`, `pytest`. Реально используемые пакеты — см. список выше.
- **`routers/sst.py`** и **`routers/gfs_forecast.py`** — не подключены в `app.py` (нет в `_try_include`), дублируют логику, которая давно живёт inline в `app.py`. Мёртвый код.
- **`services/smb_gfs.py`** и **`services/gfs_simulator.py`** — нигде не импортируются, недостижимы.
- **`data/s1.npz`, `data/s4.npz`** отсутствуют — секции «клим. среднее» и «дисперсия» вернут 500 без повторного запуска `precompute.py`.
- **`data/regions.geojson`** отсутствует в репозитории — `/api/regions` не найдёт файл, пока его не добавить вручную.
- **`render.yaml`** описывает деплой старой версии (`sst-dashboard-v5`, только `precompute.py` + Postgres не поднимается) — не отражает текущую архитектуру с БД и планировщиком.

---

## Структура файлов

```
sst_dashboard_v6/
├── app.py                  # FastAPI: lifespan, роутеры, inline SST/GFS API, статика
├── auth.py                 # JWT-логин/рефреш/me
├── config.py                # чтение .env
├── db.py                    # asyncpg pool
├── models.py                 # Pydantic-схемы ответов
├── migrate.py                 # DDL — 13 таблиц
├── seed.py                    # демо-данные
├── precompute.py               # предвычисление data/*.npz из .nc (вручную)
├── recompute_s5.py              # пересчёт тренда дисперсии
├── precompute_coastline.py       # береговая линия / ocean_mask
├── docker-compose.yml             # Postgres + n8n
├── render.yaml                     # деплой (устарел, см. «Технический долг»)
├── routers/
│   ├── stations.py, forecast.py, monitoring.py, requests.py,
│   │   calendar_routes.py, equipment.py, users.py, regions.py,
│   │   schedule.py, webhooks.py        # 10 подключённых роутеров
│   └── sst.py, gfs_forecast.py         # НЕ подключены (мёртвый код)
├── services/
│   ├── scheduler.py, data_generator.py, prophet_forecast.py,
│   │   serendipity.py, gee_gfs.py, gigachat.py, notification.py,
│   │   telegram_bot.py                 # активно используются
│   └── smb_gfs.py, gfs_simulator.py    # не используются
├── tests/
│   ├── test_calendar_security.py       # 401 без авторизации
│   └── test_schedule_security.py       # 401 без авторизации + нет утечки phone
├── data/                     # .npz/.npy/.geojson кэш для карт ТПО
└── static/
    ├── index.html             # SPA: карта, ИИ-прогноз, мониторинг, календарь, заявки
    ├── app.js, auth.js, analytics.js, cabinet.js, calendar.js,
    │   forecast.js, gfs_overlay.js, monitoring.js, regions.js,
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
