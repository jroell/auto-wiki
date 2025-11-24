#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$ROOT_DIR/.devserver"
mkdir -p "$PID_DIR"

API_LOG="${API_LOG:-/tmp/deepwiki-api.log}"
WEB_LOG="${WEB_LOG:-/tmp/deepwiki-web.log}"
API_PID="$PID_DIR/api.pid"
WEB_PID="$PID_DIR/web.pid"
API_PORT="${API_PORT:-8001}"
WEB_PORT="${WEB_PORT:-3001}"

kill_port_listeners() {
  local port="$1"
  local pids
  pids=$(lsof -i :"$port" -sTCP:LISTEN -t 2>/dev/null | tr '\n' ' ' || true)
  if [ -n "${pids:-}" ]; then
    kill $pids 2>/dev/null || true
  fi
}

start_backend() {
  # Export .env values into the environment for the subprocess
  set -a
  . "$ROOT_DIR/.env"
  set +a
  if lsof -i :"$API_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Backend port $API_PORT already in use; not starting."
    return 1
  fi
  echo "Starting backend on port $API_PORT..."
  (cd "$ROOT_DIR" && PYTHONPATH="$ROOT_DIR" poetry -C api run python -m api.main >"$API_LOG" 2>&1 & echo $! >"$API_PID")
  echo "Backend log: $API_LOG"
}

start_frontend() {
  if lsof -i :"$WEB_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Frontend port $WEB_PORT already in use; not starting."
    return 1
  fi
  echo "Starting frontend on port $WEB_PORT..."
  (cd "$ROOT_DIR" && npm run dev -- --hostname 0.0.0.0 --port "$WEB_PORT" >"$WEB_LOG" 2>&1 & echo $! >"$WEB_PID")
  echo "Frontend log: $WEB_LOG"
}

stop_backend() {
  # Kill tracked pid
  if [ -f "$API_PID" ] && kill -0 "$(cat "$API_PID")" 2>/dev/null; then
    kill "$(cat "$API_PID")" 2>/dev/null || true
    rm -f "$API_PID"
  fi
  # Kill any stray uvicorn/api.main processes
  pkill -f "python -m api.main" 2>/dev/null || true
  pkill -f "uvicorn.*api.api:app" 2>/dev/null || true
  kill_port_listeners "$API_PORT"
  # Wait briefly for port to free
  sleep 1
  if lsof -i :"$API_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Backend port $API_PORT still in use; manual cleanup may be required."
  else
    echo "Stopped backend."
  fi
}

stop_frontend() {
  if [ -f "$WEB_PID" ] && kill -0 "$(cat "$WEB_PID")" 2>/dev/null; then
    kill "$(cat "$WEB_PID")" 2>/dev/null || true
    rm -f "$WEB_PID"
  fi
  pkill -f "next dev" 2>/dev/null || true
  pkill -f "turbopack" 2>/dev/null || true
  kill_port_listeners "$WEB_PORT"
  sleep 1
  if lsof -i :"$WEB_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Frontend port $WEB_PORT still in use; manual cleanup may be required."
  else
    echo "Stopped frontend."
  fi
}

status() {
  if [ -f "$API_PID" ] && kill -0 "$(cat "$API_PID")" 2>/dev/null; then
    echo "Backend: running (pid $(cat "$API_PID"))"
  else
    echo "Backend: stopped"
  fi
  if [ -f "$WEB_PID" ] && kill -0 "$(cat "$WEB_PID")" 2>/dev/null; then
    echo "Frontend: running (pid $(cat "$WEB_PID"))"
  else
    echo "Frontend: stopped"
  fi
}

case "${1:-}" in
  start)
    start_backend
    start_frontend
    ;;
  stop)
    stop_frontend
    stop_backend
    ;;
  status)
    status
    ;;
  restart)
    stop_frontend
    stop_backend
    start_backend
    start_frontend
    ;;
  *)
    echo "Usage: $0 {start|stop|status|restart}"
    exit 1
    ;;
esac
