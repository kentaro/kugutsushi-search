#!/bin/bash
set -euo pipefail

#=============================================================================
# Kugutsushi Search - Local Development Server
#=============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

readonly IMAGE_NAME="kugutsushi-search"
readonly CONTAINER_NAME="kugutsushi-search-dev"
readonly PORT="${PORT:-8000}"

# Colors
readonly GREEN='\033[0;32m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()   { echo -e "${GREEN}[OK]${NC} $*"; }

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Run Kugutsushi Search locally for development

Options:
    -r, --rebuild    Force rebuild the image
    -s, --stop       Stop the running container
    -h, --help       Show this help

Environment variables:
    PORT             Server port (default: 8000)
EOF
}

stop_container() {
    if docker ps -q --filter "name=$CONTAINER_NAME" | grep -q .; then
        log_info "Stopping container..."
        docker stop "$CONTAINER_NAME" >/dev/null
        docker rm "$CONTAINER_NAME" >/dev/null
        log_ok "Container stopped"
    else
        log_info "Container not running"
    fi
}

run_dev() {
    local rebuild=$1

    cd "$PROJECT_DIR"

    # Stop existing container
    stop_container

    # Build if needed
    if [[ "$rebuild" == "true" ]] || ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
        log_info "Building image..."
        docker build -t "$IMAGE_NAME" .
    fi

    # Start container
    log_info "Starting development server..."
    docker run -d \
        --name "$CONTAINER_NAME" \
        -p "$PORT:8000" \
        -v "$PROJECT_DIR:/app" \
        -e PYTHONPATH=/app \
        -e DEBUG=1 \
        "$IMAGE_NAME" \
        python -m src.main

    echo ""
    log_ok "Server running at http://localhost:$PORT"
    echo ""
    log_info "Following logs (Ctrl+C to exit)..."
    echo ""

    docker logs -f "$CONTAINER_NAME"
}

main() {
    local rebuild=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            -r|--rebuild) rebuild=true ;;
            -s|--stop)    stop_container; exit 0 ;;
            -h|--help)    show_help; exit 0 ;;
            *)
                echo "Unknown option: $1" >&2
                show_help
                exit 1
                ;;
        esac
        shift
    done

    run_dev "$rebuild"
}

main "$@"
