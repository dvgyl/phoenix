#!/bin/sh

phoenix_mount=/Volumes/PhoenixWork
phoenix_bundle='/Volumes/Extreme Pro/Phoenix/phoenix-work.sparsebundle'

if ! /sbin/mount | /usr/bin/grep -Fq " on $phoenix_mount (apfs,"; then
    /usr/bin/hdiutil attach -nobrowse -mountpoint "$phoenix_mount" "$phoenix_bundle" || return 1
fi

if [ ! -f "$phoenix_mount/.phoenix-workspace" ]; then
    printf '%s\n' "The Phoenix workspace image is unavailable at $phoenix_mount." >&2
    return 1
fi

export PHOENIX_ROOT="$phoenix_mount"
export TMPDIR="$PHOENIX_ROOT/tmp"
export XDG_CACHE_HOME="$PHOENIX_ROOT/cache"
export XDG_DATA_HOME="$PHOENIX_ROOT/data"
export XDG_CONFIG_HOME="$PHOENIX_ROOT/config"
export PIP_CACHE_DIR="$XDG_CACHE_HOME/pip"
export UV_CACHE_DIR="$XDG_CACHE_HOME/uv"
export UV_PYTHON_INSTALL_DIR="$PHOENIX_ROOT/tools/python"
export CARGO_HOME="$PHOENIX_ROOT/tools/cargo"
export RUSTUP_HOME="$PHOENIX_ROOT/tools/rustup"
export npm_config_cache="$XDG_CACHE_HOME/npm"
export HOMEBREW_CACHE="$XDG_CACHE_HOME/homebrew"
export GRADLE_USER_HOME="$PHOENIX_ROOT/tools/gradle"
export GHIDRA_INSTALL_DIR="$PHOENIX_ROOT/tools/ghidra"
export COLIMA_HOME="$PHOENIX_ROOT/vm/colima"
export LIMA_HOME="$COLIMA_HOME/_lima"
export DOCKER_CONFIG="$PHOENIX_ROOT/config/docker"
export DOCKER_HOST="unix://$COLIMA_HOME/default/docker.sock"
export PYTHONPYCACHEPREFIX="$XDG_CACHE_HOME/pycache"
export PRE_COMMIT_HOME="$XDG_CACHE_HOME/pre-commit"

mkdir -p "$TMPDIR" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" "$DOCKER_CONFIG" "$PHOENIX_ROOT/tools" "$COLIMA_HOME" || return 1
unset phoenix_mount phoenix_bundle
