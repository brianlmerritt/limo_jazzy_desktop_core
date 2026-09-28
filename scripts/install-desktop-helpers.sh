#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
mkdir -p "$bin_dir"
for name in llama limo-sim ros-sim; do
  target="$bin_dir/$name"
  source="$repo_root/scripts/desktop-runtime.sh"
  if [[ -e "$target" || -L "$target" ]] && [[ "$(readlink -f -- "$target")" != "$source" ]]; then
    echo "Refusing to replace existing $target; move it aside explicitly first." >&2
    exit 1
  fi
done
for name in llama limo-sim ros-sim; do
  ln -sfn -- "$repo_root/scripts/desktop-runtime.sh" "$bin_dir/$name"
done
echo "Installed llama, limo-sim and ros-sim in $bin_dir; existing isaac launcher preserved."
