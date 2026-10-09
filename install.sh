#!/bin/sh
# superai-skills one-click installer. Usage: curl -fsSL <raw install.sh url> | sh [-s -- init-flags]
# Env: SUPERAI_HOME (clone dir). --dry-run prints the steps and runs nothing; other flags go to the
# `init` wizard (-y/--yes, --only, --skip, ...). The wizard prompts via the terminal even under `curl | sh`;
# with no terminal at all it runs with --no-input (recommended steps only).
set -eu

REPO="https://github.com/ml-lubich/superai-skills.git"
DIR="${SUPERAI_HOME:-$HOME/dev/superai-skills}"
TTY="${SUPERAI_TTY:-/dev/tty}"
DRY=0
for a in "$@"; do [ "$a" = "--dry-run" ] || [ "$a" = "-n" ] && DRY=1; done

step() {
  echo "==> $*"
  [ "$DRY" = 1 ] || "$@"
}

if ! command -v uv >/dev/null 2>&1; then
  echo "==> install uv"
  if [ "$DRY" != 1 ]; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  fi
fi
# uv tool installs land in ~/.local/bin, which may not be on PATH even when uv already was.
PATH="$HOME/.local/bin:$PATH"
export PATH
echo "==> if \`superai-skills\` is not found in new shells, run: uv tool update-shell"

if [ -d "$DIR/.git" ]; then
  step git -C "$DIR" pull --ff-only
  step git -C "$DIR" submodule update --init --recursive
else
  step git clone --recurse-submodules "$REPO" "$DIR"
fi

if [ "$DRY" = 1 ]; then
  echo "==> cd $DIR"
else
  cd "$DIR"
fi
step uv tool install --editable --force .
if [ "$DRY" = 1 ]; then
  step superai-skills init "$@"
elif [ -t 0 ]; then
  superai-skills init "$@"
elif [ -r "$TTY" ] && ( : <"$TTY" ) 2>/dev/null; then
  superai-skills init "$@" <"$TTY"
else
  echo "==> no terminal available: running init with --no-input"
  superai-skills init "$@" --no-input
fi
