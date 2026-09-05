# Interactive Bash startup for scripts/ros-shell.sh.
if [[ -r "$HOME/.bashrc" ]]; then
  source "$HOME/.bashrc"
fi
if ! source /workspace/scripts/ros-env.sh; then
  echo "ROS shell setup failed; fix the workspace build before running ROS commands." >&2
  exit 1
fi
