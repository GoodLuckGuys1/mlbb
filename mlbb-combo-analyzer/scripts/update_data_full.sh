#!/bin/bash
# Полное обновление: все герои + синергии + контрпики + мета
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"

STATUS_FILE="$ROOT/data/refresh_status.json"
LOG_FILE="$ROOT/data/update.log"
mkdir -p "$ROOT/data"

python3 -c "from refresh_status import start_refresh; start_refresh('full', 'Полная синхронизация...')"

{
  echo "=== FULL $(date) ==="
  python3 -m pip install -q -r backend/requirements.txt
  python3 backend/sync_data.py
  python3 backend/patch_meta.py
  python3 backend/patch_roles.py
  cd backend && python3 -c "from cache_utils import stamp_cache; print('updated_at', stamp_cache())"
  cd "$ROOT"
  heroes=$(python3 -c "import json; print(len(json.load(open('data/cache.json'))['heroes']))")
  python3 -c "from refresh_status import finish_refresh; finish_refresh(True, 'Полное обновление завершено', $heroes)"
  curl -s -X POST http://127.0.0.1:8000/api/reload >/dev/null 2>&1 || true
} >> "$LOG_FILE" 2>&1 || {
  python3 -c "from refresh_status import finish_refresh; finish_refresh(False, 'Ошибка полного обновления')"
  exit 1
}
