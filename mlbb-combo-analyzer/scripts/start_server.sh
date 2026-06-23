#!/bin/bash
# Запуск сайта MLBB Combo Analyzer
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Установка зависимостей..."
python3 -m pip install -q -r backend/requirements.txt

if [ ! -f data/cache.json ]; then
  echo "Кэш не найден. Собираю стартовый кэш..."
  python3 backend/build_seed_cache.py
  python3 -c "from backend.cache_utils import stamp_cache; stamp_cache()"
  echo "Для полной базы: ./scripts/update_data_full.sh"
fi

echo ""
echo "Сервер: http://127.0.0.1:8000"
echo "Остановка: Ctrl+C"
echo ""

cd backend
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
