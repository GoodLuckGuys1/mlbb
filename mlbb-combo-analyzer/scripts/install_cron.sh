#!/bin/bash
# Установка cron: ежедневно в 6:00 + полное обновление по воскресеньям в 5:00
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DAILY="$ROOT/scripts/update_data.sh"
FULL="$ROOT/scripts/update_data_full.sh"
chmod +x "$DAILY" "$FULL" "$ROOT/scripts/start_server.sh"

CRON_DAILY="0 6 * * * $DAILY >> $ROOT/data/cron.log 2>&1"
CRON_FULL="0 5 * * 0 $FULL >> $ROOT/data/cron.log 2>&1"

TMP="$(mktemp)"
crontab -l 2>/dev/null | grep -v "mlbb-combo-analyzer" > "$TMP" || true
echo "# mlbb-combo-analyzer daily meta update" >> "$TMP"
echo "$CRON_DAILY" >> "$TMP"
echo "# mlbb-combo-analyzer weekly full sync" >> "$TMP"
echo "$CRON_FULL" >> "$TMP"
crontab "$TMP"
rm "$TMP"

echo "Cron установлен:"
echo "  Ежедневно 06:00 — $DAILY"
echo "  Воскресенье 05:00 — $FULL"
echo "Лог: $ROOT/data/cron.log"
