#!/bin/bash
# Ежедневное обновление: мета (пики/баны) + роли/линии + русские имена
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"

STATUS_FILE="$ROOT/data/refresh_status.json"
LOG_FILE="$ROOT/data/update.log"
mkdir -p "$ROOT/data"

python3 -c "from refresh_status import start_refresh; start_refresh('incremental', 'Обновление данных...')"

{
  echo "=== $(date) ==="
  python3 -m pip install -q -r backend/requirements.txt

  if [ ! -f data/cache.json ]; then
    echo "Кэш не найден, полная синхронизация..."
    python3 backend/sync_data.py
  else
    echo "Обновление меты (пики/баны/винрейт)..."
    python3 backend/patch_meta.py
    echo "Обновление ролей и линий..."
    python3 backend/patch_roles.py
    echo "Обновление русских имён..."
    python3 backend/patch_ru_names.py
  fi

  cd backend && python3 -c "from cache_utils import stamp_cache; print('updated_at', stamp_cache())"
  cd "$ROOT"

  heroes=$(python3 -c "import json; print(len(json.load(open('data/cache.json'))['heroes']))")
  python3 -c "from refresh_status import finish_refresh; finish_refresh(True, 'Данные обновлены', $heroes)"

  curl -s -X POST http://127.0.0.1:8000/api/reload >/dev/null 2>&1 || true
} >> "$LOG_FILE" 2>&1 || {
  python3 -c "from refresh_status import finish_refresh; finish_refresh(False, 'Ошибка обновления, см. data/update.log')"
  exit 1
}
