#!/usr/bin/env bash
set -uo pipefail

#
# Report trailing whitespace in source files while ignoring generated
# directories such as Git metadata, virtual environments and caches.
#
# Usage:
#   check-whitespace.sh
#
# Exit codes:
#   0  No trailing whitespace found.
#   1  Trailing whitespace found.
#   2  Runtime error.
#

readonly SEARCH_ROOT="."

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

check_dependencies() {
  require_command find
  require_command grep
}

check_whitespace() {
  find "$SEARCH_ROOT" \
    \( \
      -name .git -o \
      -name .venv -o \
      -name __pycache__ -o \
      -name .mypy_cache -o \
      -name .pytest_cache \
    \) -prune -o \
    -type f \
    \( \
      -name "*.py" -o \
      -name "*.yaml" -o \
      -name "*.yml" -o \
      -name "*.md" \
    \) \
    -exec grep -nH '[[:blank:]]$' {} +
}

main() {

  local output

  check_dependencies

  output="$(check_whitespace 2>/dev/null)" || {
    local status=$?

    if [[ "$status" -ne 1 ]]; then
      die "Unable to check files for trailing whitespace."
    fi
  }

  if [[ -n "$output" ]]; then
    printf '%s\n' "$output"
    printf '\n'
    printf 'Trailing whitespace found.\n'
    exit 1
  fi

  printf 'No trailing whitespace found.\n'
  exit 0

}

main "$@"
exit $?