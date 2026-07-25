#!/usr/bin/env bash
set -uo pipefail

#
# Verify that the Git revision deployed by
# Argo CD matches the current local Git HEAD.
#
# Usage:
#   argocd-git-revision-check.sh
#   argocd-git-revision-check.sh --all
#   argocd-git-revision-check.sh <application>
#
# Exit codes:
#   0  All checked applications match the local Git revision.
#   1  One or more applications differ.
#   2  Usage or runtime error.
#

readonly ARGOCD_NAMESPACE="argocd"

CHECK_ALL=false
APPLICATION=""
USE_COLOR=false

readonly GREEN=$'\033[32m'
readonly RED=$'\033[31m'
readonly YELLOW=$'\033[33m'
readonly RESET=$'\033[0m'

readonly APP_WIDTH=32
readonly FIELD_WIDTH=10

init_colors() {
  if [[ -t 1 ]]; then
    USE_COLOR=true
  fi
}

usage() {
  printf 'Usage: %s [--all] [APPLICATION]\n' "$(basename "$0")"
  printf '\n'
  printf 'Examples:\n'
  printf '  %s\n' "$(basename "$0")"
  printf '  %s --all\n' "$(basename "$0")"
  printf '  %s traefik\n' "$(basename "$0")"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --all)
        CHECK_ALL=true
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      -*)
        usage
        die "Unknown option: $1"
        ;;
      *)
        if [[ -n "$APPLICATION" ]]; then
          usage
          die "Only one application may be specified."
        fi
        APPLICATION="$1"
        ;;
    esac

    shift
  done
  if [[ -z "$APPLICATION" ]]; then
    CHECK_ALL=true
  fi
}

check_dependencies() {
  require_command git
  require_command kubectl
  require_command jq
}

get_local_revision() {
  git rev-parse HEAD 2>/dev/null || die "Unable to determine local Git revision."
}

get_short_revision() {
  printf '%s' "$1" | cut -c1-7
}

get_local_branch() {
  git branch --show-current 2>/dev/null || echo "-"
}

get_repository_name() {
  basename -s .git "$(git remote get-url origin)"
}

get_application_json() {
  local app="$1"
  kubectl get application \
    "$app" \
    -n "$ARGOCD_NAMESPACE" \
    -o json 2>/dev/null || \
    die "Unable to retrieve Argo CD Application '$app'."
}

get_application_list() {
  kubectl get applications \
    -n "$ARGOCD_NAMESPACE" \
    -o json |
  jq -r '.items[].metadata.name'
}

get_git_revision_from_json() {
  local json="$1"
  jq -r '
    if (.spec.sources? | type) == "array" then
      (.spec.sources // []) as $sources
      | (.status.sync.revisions // []) as $revisions
      | first(
          range(0; $sources | length) as $index
          | select(($sources[$index].chart // null) == null)
          | $revisions[$index] // empty
        )
    elif (.spec.source.chart // null) == null then
      .status.sync.revision // empty
    else
      empty
    end
  ' <<<"$json"
}

get_health() {
  jq -r '.status.health.status // "-"' <<<"$1"
}

get_sync_status() {
  jq -r '.status.sync.status // "-"' <<<"$1"
}

print_header() {
  printf 'Repository : %s\n' "$(get_repository_name)"
  printf 'Branch     : %s\n' "$(get_local_branch)"
  printf 'Revision   : %s\n' "$(get_short_revision "$LOCAL_REVISION")"
  printf '\n'
  printf '%-32s %-10s %-10s %-10s %s\n' \
    "APPLICATION" \
    "HEALTH" \
    "SYNC" \
    "GIT REV" \
    "HEAD MATCH"
  printf '%-32s %-10s %-10s %-10s %s\n' \
    "--------------------------------" \
    "----------" \
    "----------" \
    "----------" \
    "----------"
}

print_field() {
  local value="$1"
  local width="$2"
  local category="$3"
  local color=""
  if $USE_COLOR; then
    case "${category}:${value}" in
      health:Healthy)
        color="$GREEN"
        ;;
      health:Degraded)
        color="$RED"
        ;;
      health:Progressing|health:Suspended|health:Missing|health:Unknown)
        color="$YELLOW"
        ;;
      sync:Synced)
        color="$GREEN"
        ;;
      sync:OutOfSync)
        color="$RED"
        ;;
      sync:Unknown)
        color="$YELLOW"
        ;;
      result:MATCH)
        color="$GREEN"
        ;;
      result:DIFFERS)
        color="$RED"
        ;;
      result:CHART\ ONLY)
        color="$YELLOW"
        ;;
    esac
  fi
  if [[ -n "$color" ]]; then
    printf '%s%-*s%s' "$color" "$width" "$value" "$RESET"
  else
    printf '%-*s' "$width" "$value"
  fi
}

check_application() {
  local app="$1"
  local json
  local health
  local sync
  local git_revision
  local display_revision
  local result
  ((APPLICATIONS_CHECKED++))
  json="$(get_application_json "$app")"
  health="$(get_health "$json")"
  sync="$(get_sync_status "$json")"
  git_revision="$(get_git_revision_from_json "$json")"
  if [[ -z "$git_revision" ]]; then
    display_revision="-"
    result="CHART ONLY"
  elif [[ "$git_revision" == "$LOCAL_REVISION" ]]; then
    display_revision="$(get_short_revision "$git_revision")"
    result="MATCH"
  else
    display_revision="$(get_short_revision "$git_revision")"
    result="DIFFERS"
    STATUS=1
    ((APPLICATIONS_DIFFER++))
  fi
  printf '%-*s ' "$APP_WIDTH" "$app"
  print_field "$health" "$FIELD_WIDTH" health
  printf ' '
  print_field "$sync" "$FIELD_WIDTH" sync
  printf ' '
  printf '%-*s ' "$FIELD_WIDTH" "$display_revision"
  print_field "$result" "$FIELD_WIDTH" result
  printf '\n'
}

print_summary() {
  printf '\n'
  if [[ "$APPLICATIONS_CHECKED" -eq 1 ]]; then
    printf 'Checked 1 application.\n'
  else
    printf 'Checked %d applications.\n' "$APPLICATIONS_CHECKED"
  fi
  if [[ "$APPLICATIONS_DIFFER" -eq 0 ]]; then
    printf 'All applications match the local Git revision.\n'
  elif [[ "$APPLICATIONS_DIFFER" -eq 1 ]]; then
    printf '1 application differs from the local Git revision.\n'
  else
    printf '%d applications differ from the local Git revision.\n' "$APPLICATIONS_DIFFER"
  fi
}

main() {
  local app
  parse_args "$@"
  check_dependencies
  init_colors
  LOCAL_REVISION="$(get_local_revision)"
  STATUS=0
  APPLICATIONS_CHECKED=0
  APPLICATIONS_DIFFER=0
  print_header
  if $CHECK_ALL; then
    while read -r app; do
      [[ -z "$app" ]] && continue
      check_application "$app"
    done < <(get_application_list | sort)
  else
    check_application "$APPLICATION"
  fi
  print_summary
  exit "$STATUS"
}

main "$@"
exit $?
