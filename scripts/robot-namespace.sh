#!/usr/bin/env bash
# Source this from framework helpers; components receive native ROS interfaces.
# Explicit environment wins, then generated .env, then legacy root namespace.
if [[ ! -v LIMO_ROS_NAMESPACE ]]; then
  namespace_env="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.env"
  LIMO_ROS_NAMESPACE=""
  if [[ -r "$namespace_env" ]]; then
    while IFS='=' read -r key value; do
      [[ "$key" != LIMO_ROS_NAMESPACE ]] || LIMO_ROS_NAMESPACE="$value"
    done < "$namespace_env"
  fi
fi
[[ -z "$LIMO_ROS_NAMESPACE" || "$LIMO_ROS_NAMESPACE" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]] || {
  echo "Invalid LIMO_ROS_NAMESPACE: expected one ROS namespace token" >&2
  return 1
}
export LIMO_ROS_NAMESPACE
ROBOT_PREFIX="${LIMO_ROS_NAMESPACE:+/$LIMO_ROS_NAMESPACE}"
