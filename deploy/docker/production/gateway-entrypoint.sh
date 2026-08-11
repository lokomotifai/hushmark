#!/bin/sh
set -eu

read_required_secret() {
  secret_path=$1
  variable_name=$2
  if [ ! -r "$secret_path" ]; then
    echo "required secret is not readable: $variable_name" >&2
    exit 1
  fi
  secret_value=$(tr -d '\r\n' <"$secret_path")
  if [ -z "$secret_value" ]; then
    echo "required secret is empty: $variable_name" >&2
    exit 1
  fi
  export "$variable_name=$secret_value"
}

read_optional_secret() {
  secret_path=$1
  variable_name=$2
  if [ ! -r "$secret_path" ]; then
    return
  fi
  secret_value=$(tr -d '\r\n' <"$secret_path")
  if [ -n "$secret_value" ]; then
    export "$variable_name=$secret_value"
  fi
}

read_required_secret /run/secrets/hushmark_api_keys HUSHMARK_API_KEYS
read_optional_secret /run/secrets/openai_api_key HUSHMARK_OPENAI_API_KEY
read_optional_secret /run/secrets/anthropic_api_key HUSHMARK_ANTHROPIC_API_KEY

exec node node_modules/@hushmark/gateway/dist/cli.js
