#!/usr/bin/env bash

bootstrap_log() {
  printf '[bootstrap] %s\n' "$*"
}

bootstrap_die() {
  printf '[bootstrap] error: %s\n' "$*" >&2
  exit 2
}
