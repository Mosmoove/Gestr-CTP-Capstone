#!/bin/bash
set -euo pipefail

on_error() {
    result=$?
    printf '\nThe collector could not start. Read the message above.\n'
    read -r -p 'Press Return to close...' || true
    exit "$result"
}
trap on_error ERR

if [[ "$(uname -s)" != "Darwin" ]]; then
    printf 'This launcher is for macOS. On Windows, use Collect Gestures.cmd.\n'
    exit 1
fi

project_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
case "$(uname -m)" in
    arm64) architecture='aarch64' ;;
    x86_64) architecture='x86_64' ;;
    *) printf 'This launcher supports Apple Silicon and Intel Macs.\n'; exit 1 ;;
esac

runtime_dir="$HOME/Library/Application Support/GestrRuntime/$architecture"
tools_dir="$runtime_dir/tools"
uv_path="$tools_dir/uv"
python_path="$runtime_dir/venv/bin/python"
requirements_path="$project_dir/requirements-collector.txt"
stamp_path="$runtime_dir/collector-requirements.sha256"
mkdir -p "$tools_dir"

if [[ ! -x "$uv_path" ]]; then
    printf 'First launch: downloading the Python setup tool...\n'
    uv_version='0.13.8'
    archive_name="uv-$architecture-apple-darwin"
    archive_path="$runtime_dir/$archive_name.tar.gz"
    curl --fail --location --retry 2 \
        "https://github.com/astral-sh/uv/releases/download/$uv_version/$archive_name.tar.gz" \
        --output "$archive_path"
    tar -xzf "$archive_path" -C "$tools_dir" --strip-components=1 "$archive_name/uv"
    chmod +x "$uv_path"
fi

if [[ ! -x "$python_path" ]]; then
    printf 'First launch: setting up an isolated Python 3.12 environment...\n'
    "$uv_path" --system-certs venv "$runtime_dir/venv" --python 3.12 --managed-python
fi

requirements_hash="$(shasum -a 256 "$requirements_path" | awk '{print $1}')"
installed_hash=''
if [[ -f "$stamp_path" ]]; then
    installed_hash="$(cat "$stamp_path")"
fi
if [[ "$requirements_hash" != "$installed_hash" ]]; then
    printf 'Installing camera libraries. The first launch can take a few minutes...\n'
    "$uv_path" --system-certs pip install --python "$python_path" -r "$requirements_path"
    printf '%s\n' "$requirements_hash" > "$stamp_path"
fi

cd "$project_dir"
"$python_path" -m collector.app
