#!/bin/bash
set -euo pipefail

#=============================================================================
# Kugutsushi Search - Deploy Script
#=============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
readonly LOCAL_IMAGE_DIR="$SCRIPT_DIR"

# Remote host configuration
readonly REMOTE_HOST="${REMOTE_HOST:-raspberrypi.local}"
readonly REMOTE_USER="${REMOTE_USER:-kentaro}"
readonly APP_NAME="kugutsushi-search"
readonly REMOTE_APP_DIR="\$HOME/apps/$APP_NAME"
readonly LOCAL_IMAGE_PATH="$LOCAL_IMAGE_DIR/image.tar"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

#-----------------------------------------------------------------------------
# Helper functions
#-----------------------------------------------------------------------------

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

run_remote() {
    ssh -o ConnectTimeout=10 "$REMOTE_USER@$REMOTE_HOST" "$@"
}

copy_to_remote() {
    scp -o ConnectTimeout=10 "$1" "$REMOTE_USER@$REMOTE_HOST:$2"
}

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Deploy Kugutsushi Search to Raspberry Pi

Options:
    -b, --build             Build Docker image for ARM64
    -e, --embeddings        Upload embeddings data
    -d, --deploy            Deploy only (skip file transfers)
    -a, --all               Build + Upload embeddings + Deploy
    -s, --status            Show remote container status
    -l, --logs              Show remote container logs
    -h, --help              Show this help

Environment variables:
    REMOTE_HOST             Remote host (default: raspberrypi.local)
    REMOTE_USER             Remote user (default: kentaro)

Examples:
    $(basename "$0") --build --deploy     # Build and deploy
    $(basename "$0") --all                # Full deployment
    $(basename "$0") --embeddings         # Upload embeddings only
    $(basename "$0") --logs               # View logs
EOF
}

#-----------------------------------------------------------------------------
# Build
#-----------------------------------------------------------------------------

build_image() {
    log_info "Building Docker image for linux/arm64..."

    cd "$PROJECT_DIR"

    # Setup buildx if needed
    if ! docker buildx inspect builder &>/dev/null; then
        docker buildx create --use --name builder
    fi

    docker buildx build \
        --platform linux/arm64 \
        --tag "$APP_NAME" \
        --load \
        .

    log_info "Saving image to $LOCAL_IMAGE_PATH..."
    docker save "$APP_NAME" > "$LOCAL_IMAGE_PATH"

    local size
    size=$(du -h "$LOCAL_IMAGE_PATH" | cut -f1)
    log_ok "Image saved ($size)"
}

#-----------------------------------------------------------------------------
# Upload
#-----------------------------------------------------------------------------

upload_image() {
    if [[ ! -f "$LOCAL_IMAGE_PATH" ]]; then
        log_error "Image not found: $LOCAL_IMAGE_PATH"
        log_error "Run with --build first"
        exit 1
    fi

    log_info "Uploading Docker image..."
    run_remote "mkdir -p $REMOTE_APP_DIR"
    copy_to_remote "$LOCAL_IMAGE_PATH" "$REMOTE_APP_DIR/image.tar"
    log_ok "Image uploaded"
}

upload_embeddings() {
    local embeddings_dir="$PROJECT_DIR/embeddings"

    if [[ ! -d "$embeddings_dir" ]]; then
        log_error "Embeddings directory not found: $embeddings_dir"
        exit 1
    fi

    log_info "Uploading embeddings..."
    run_remote "mkdir -p $REMOTE_APP_DIR/embeddings"

    # Use rsync for efficient transfer
    rsync -avz --progress \
        "$embeddings_dir/" \
        "$REMOTE_USER@$REMOTE_HOST:$REMOTE_APP_DIR/embeddings/"

    log_ok "Embeddings uploaded"
}

#-----------------------------------------------------------------------------
# Deploy
#-----------------------------------------------------------------------------

deploy() {
    log_info "Deploying to $REMOTE_HOST..."

    run_remote bash << 'REMOTE_SCRIPT'
        set -euo pipefail

        APP_NAME="kugutsushi-search"
        APP_DIR="$HOME/apps/$APP_NAME"

        echo "Stopping existing container..."
        docker rm -f "$APP_NAME" 2>/dev/null || true

        echo "Loading image..."
        docker load < "$APP_DIR/image.tar"

        echo "Starting container..."
        docker run -d \
            --name "$APP_NAME" \
            --restart unless-stopped \
            -p 8000:8000 \
            -v "$APP_DIR/embeddings:/app/embeddings" \
            --memory=5g \
            --cpus=2 \
            "$APP_NAME"

        echo "Waiting for startup..."
        sleep 3

        if docker ps | grep -q "$APP_NAME"; then
            echo "Container is running"
        else
            echo "Container failed to start"
            docker logs "$APP_NAME"
            exit 1
        fi
REMOTE_SCRIPT

    log_ok "Deployed successfully"
    echo ""
    log_info "Access: http://$REMOTE_HOST:8000"
}

#-----------------------------------------------------------------------------
# Status & Logs
#-----------------------------------------------------------------------------

show_status() {
    log_info "Container status on $REMOTE_HOST:"
    echo ""
    run_remote "docker ps -a --filter name=$APP_NAME --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
}

show_logs() {
    log_info "Logs from $REMOTE_HOST:"
    run_remote "docker logs --tail 100 -f $APP_NAME"
}

#-----------------------------------------------------------------------------
# Main
#-----------------------------------------------------------------------------

main() {
    local do_build=false
    local do_embeddings=false
    local do_deploy=false
    local do_status=false
    local do_logs=false

    if [[ $# -eq 0 ]]; then
        show_help
        exit 0
    fi

    while [[ $# -gt 0 ]]; do
        case $1 in
            -b|--build)      do_build=true ;;
            -e|--embeddings) do_embeddings=true ;;
            -d|--deploy)     do_deploy=true ;;
            -a|--all)        do_build=true; do_embeddings=true; do_deploy=true ;;
            -s|--status)     do_status=true ;;
            -l|--logs)       do_logs=true ;;
            -h|--help)       show_help; exit 0 ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
        shift
    done

    # Execute requested actions
    $do_status && { show_status; exit 0; }
    $do_logs && { show_logs; exit 0; }
    $do_build && build_image
    $do_build && upload_image
    $do_embeddings && upload_embeddings
    $do_deploy && deploy

    log_ok "Done!"
}

main "$@"
