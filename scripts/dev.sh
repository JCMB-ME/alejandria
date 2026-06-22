#!/bin/bash
# =============================================================================
# Development helper script
# =============================================================================
set -e

cmd="${1:-help}"

case "$cmd" in
  start)
    echo "Starting Alejandría (production)..."
    docker compose up -d
    echo "Open http://localhost:8080"
    ;;
  dev)
    echo "Starting Alejandría (development, hot reload)..."
    docker compose -f docker-compose.dev.yml up
    ;;
  stop)
    echo "Stopping..."
    docker compose down
    ;;
  logs)
    docker compose logs -f alejandria
    ;;
  shell)
    docker compose exec alejandria /bin/bash
    ;;
  rebuild)
    echo "Rebuilding image..."
    docker compose build --no-cache
    docker compose up -d
    ;;
  reset)
    echo "⚠️  This will DELETE your library and config. Press Ctrl-C to abort."
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      docker compose down -v
      rm -rf library config
      echo "Reset complete."
    fi
    ;;
  test)
    echo "Running tests..."
    cd backend
    if [ ! -d ".venv" ]; then
      uv venv
      uv pip install -e ".[dev]"
    fi
    source .venv/bin/activate
    pytest -v
    ;;
  test-frontend)
    echo "Running frontend tests..."
    cd frontend
    npm run check
    npm run test
    ;;
  calibre-shell)
    docker compose exec alejandria calibredb --help
    ;;
  *)
    echo "Alejandría dev helper"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  start        Start production containers (detached)"
    echo "  dev          Start dev containers (with hot reload, attached)"
    echo "  stop         Stop containers"
    echo "  logs         Tail logs"
    echo "  shell        Open shell in container"
    echo "  rebuild      Rebuild image from scratch"
    echo "  reset        Delete library and config (DESTRUCTIVE)"
    echo "  test         Run backend tests"
    echo "  test-frontend Run frontend tests + type check"
    echo "  calibre-shell Show Calibre CLI help"
    ;;
esac
