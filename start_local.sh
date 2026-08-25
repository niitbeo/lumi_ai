#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")" && pwd)"
runtime_dir="$project_dir/.run"
mkdir -p "$runtime_dir"

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] && kill -0 "$(<"$pid_file")" 2>/dev/null
}

PYTHON_BIN="$project_dir/.venv/bin/python3"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

if ! is_running "$runtime_dir/api.pid"; then
  nohup env PORTRAIT_API_PORT=8417 "$PYTHON_BIN" "$project_dir/server/server.py" >"$runtime_dir/api.log" 2>&1 &
  echo $! >"$runtime_dir/api.pid"
fi

if ! is_running "$runtime_dir/web.pid"; then
  cd "$project_dir"
  nohup node_modules/.bin/vinext dev --port 4417 >"$runtime_dir/web.log" 2>&1 &
  echo $! >"$runtime_dir/web.pid"
fi

for _ in {1..40}; do
  if curl -fsS http://127.0.0.1:8417/api/health >/dev/null 2>&1 && \
     curl -fsS http://localhost:4417/ >/dev/null 2>&1; then
    printf 'Lumi Portrait độc lập đang chạy:\n  Web: http://localhost:4417\n  API: http://127.0.0.1:8417/api/health\n'
    exit 0
  fi
  sleep 0.25
done

printf 'Khởi động chưa thành công. Xem log:\n  %s\n  %s\n' "$runtime_dir/web.log" "$runtime_dir/api.log" >&2
exit 1
