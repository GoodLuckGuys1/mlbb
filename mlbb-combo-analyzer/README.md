# MLBB Combo Analyzer

Веб-инструмент для анализа драфта Mobile Legends: Bang Bang — связки, контрпики, прогноз победителя, топы пиков/банов.

## Быстрый старт

```bash
cd /Users/coala/Projects/mlbb-combo-analyzer
chmod +x scripts/*.sh run.sh
./scripts/start_server.sh
```

Или:

```bash
./run.sh
```

Сайт: **http://127.0.0.1:8000**

## Обновление данных

### Вручную (кнопка на сайте)

Кнопка **«Обновить данные»** в шапке — запускает фоновое обновление меты и ролей (~10–20 мин).

### Скриптами

```bash
# Быстрое (пики/баны, роли, линии) — ~10–20 мин
./scripts/update_data.sh

# Полное (все герои + синергии + контрпики) — ~40–60 мин
./scripts/update_data_full.sh
```

### Автообновление (cron)

```bash
./scripts/install_cron.sh
```

Установит:
- **Ежедневно в 06:00** — `update_data.sh` (мета + роли)
- **Воскресенье в 05:00** — `update_data_full.sh` (полная синхронизация)

Лог: `data/cron.log`

## Первичная настройка

```bash
python3 -m pip install -r backend/requirements.txt

# Полная база героев (один раз)
python3 backend/sync_data.py
python3 backend/patch_meta.py
python3 backend/patch_roles.py
```

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/health` | статус, дата данных |
| POST | `/api/refresh-data` | запуск обновления |
| GET | `/api/refresh-status` | статус обновления |
| POST | `/api/reload` | перечитать кэш |
| POST | `/api/analyze` | анализ драфта |
| GET | `/api/counters/{id}` | контрпики |
| GET | `/api/meta/tops` | топы пиков/банов |

## Структура

```
mlbb-combo-analyzer/
├── scripts/
│   ├── start_server.sh      # запуск сервера
│   ├── update_data.sh       # ежедневное обновление
│   ├── update_data_full.sh  # полное обновление
│   └── install_cron.sh      # установка cron
├── backend/
├── frontend/
├── data/cache.json          # кэш + updated_at
└── run.sh
```

## Дисклеймер

Неофициальный проект. Данные из [mlbb.rone.dev](https://mlbb.rone.dev). Не связан с Moonton.
