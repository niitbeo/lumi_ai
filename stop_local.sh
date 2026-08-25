#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")" && pwd)"
runtime_dir="$project_dir/.run"

for service in web api; do
  pid_file="$runtime_dir/$service.pid"
  if [[ -f "$pid_file" ]]; then
    pid="$(<"$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid"
    fi
    rm -f "$pid_file"
  fi
done

echo "Đã dừng Lumi Portrait."
