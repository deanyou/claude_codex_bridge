#!/usr/bin/env bash
# CC_BRIDGE Status Bar Script for tmux
# Shows project cc-bridge-daemon mount state for the current pane path.

CC_BRIDGE_DIR="${CC_BRIDGE_DIR:-$HOME/.local/share/cc-bridge}"
CC_BRIDGE_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/cc-bridge"
TMP_DIR="${TMPDIR:-/tmp}"

# Color codes for tmux status bar (Tokyo Night palette)
C_GREEN="#[fg=#9ece6a,bold]"
C_ORANGE="#[fg=#ff9e64,bold]"
C_TEAL="#[fg=#7dcfff,bold]"
C_RESET="#[fg=default,nobold]"
C_DIM="#[fg=#565f89]"

resolve_project_anchor() {
    local start_path="$1"
    local current

    if [[ -z "$start_path" ]]; then
        start_path="$PWD"
    fi
    if [[ -f "$start_path" ]]; then
        current="$(dirname "$start_path")"
    else
        current="$start_path"
    fi

    while [[ -n "$current" && "$current" != "/" ]]; do
        if [[ -d "$current/.cc-bridge" ]]; then
            echo "$current"
            return 0
        fi
        current="$(dirname "$current")"
    done
    return 1
}

check_cc-bridge-daemon_mount() {
    local start_path="$1"
    local project_root=""
    local lease_file=""

    project_root="$(resolve_project_anchor "$start_path")" || {
        echo "absent"
        return 0
    }
    lease_file="$project_root/.cc-bridge/cc-bridge-daemon/lease.json"
    if [[ ! -f "$lease_file" ]]; then
        echo "absent"
        return 0
    fi
    if grep -q '"mount_state"[[:space:]]*:[[:space:]]*"mounted"' "$lease_file" 2>/dev/null; then
        echo "mounted"
    else
        echo "unmounted"
    fi
}

format_cc-bridge-daemon_status() {
    local start_path="$1"
    local state
    state="$(check_cc-bridge-daemon_mount "$start_path")"
    case "$state" in
        mounted) echo "${C_GREEN}●${C_RESET}" ;;
        absent) echo "${C_DIM}-${C_RESET}" ;;
        *) echo "${C_DIM}○${C_RESET}" ;;
    esac
}

main() {
    local mode="${1:-full}"
    local target_path="${2:-$PWD}"
    local cache_s="${CC_BRIDGE_STATUS_CACHE_S:-1}"
    local cache_suffix
    cache_suffix="$(printf '%s' "$target_path" | tr '/ ' '__' | tr -cd '[:alnum:]_.-')"
    [[ -n "$cache_suffix" ]] || cache_suffix="default"
    local cache_file="$TMP_DIR/cc-bridge-status.${mode}.${cache_suffix}.cache"

    if [[ "$cache_s" =~ ^[0-9]+$ ]] && (( cache_s > 0 )) && [[ -f "$cache_file" ]]; then
        local now ts cached
        now="$(date +%s 2>/dev/null || echo 0)"
        ts="$(head -n 1 "$cache_file" 2>/dev/null || true)"
        if [[ "$ts" =~ ^[0-9]+$ ]] && (( now - ts < cache_s )); then
            cached="$(sed -n '2p' "$cache_file" 2>/dev/null || true)"
            if [[ -n "$cached" ]]; then
                echo "$cached"
                return 0
            fi
        fi
    fi

    local out=""
    case "$mode" in
        full)
            out=" $(format_cc-bridge-daemon_status "$target_path") "
            ;;
        daemons)
            out=" $(format_cc-bridge-daemon_status "$target_path") "
            ;;
        compact)
            out="${C_ORANGE}CC_BRIDGE${C_RESET} $(format_cc-bridge-daemon_status "$target_path")"
            ;;
        modern)
            out="$(format_cc-bridge-daemon_status "$target_path")"
            ;;
        pane)
            local pane_title="${TMUX_PANE_TITLE:-}"
            local pane_title_lc
            pane_title_lc="$(printf '%s' "$pane_title" | tr '[:upper:]' '[:lower:]')"
            if [[ "$pane_title_lc" == cc-bridge-* ]]; then
                local agent_name="${pane_title#CC_BRIDGE-}"
                agent_name="${agent_name#cc-bridge-}"
                local agent_key
                agent_key="$(printf '%s' "$agent_name" | tr '[:upper:]' '[:lower:]')"
                case "$agent_key" in
                    cmd) echo "${C_TEAL}[${agent_name}]${C_RESET}" ;;
                    *) echo "${C_ORANGE}[${agent_name}]${C_RESET}" ;;
                esac
            fi
            return 0
            ;;
    esac

    if [[ -n "$out" ]]; then
        if [[ "$cache_s" =~ ^[0-9]+$ ]] && (( cache_s > 0 )); then
            local now tmp
            now="$(date +%s 2>/dev/null || echo 0)"
            tmp="${cache_file}.tmp.$$"
            {
                echo "$now"
                echo "$out"
            } > "$tmp" 2>/dev/null || true
            mv -f "$tmp" "$cache_file" 2>/dev/null || true
        fi
        echo "$out"
    fi
}

main "$@"
