#!/bin/bash
set -e

ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: .env file not found at $ENV_FILE"
  exit 1
fi

echo "Reading secrets from $ENV_FILE and setting them on fly.io..."

# Read each line from .env file, skip comments and empty lines
secrets=""
while IFS= read -r line || [ -n "$line" ]; do
  # Skip comments and empty lines
  if [[ $line =~ ^[[:space:]]*$ || $line =~ ^[[:space:]]*# ]]; then
    continue
  fi
  
  # Add to secrets string
  if [ -n "$secrets" ]; then
    secrets="$secrets $line"
  else
    secrets="$line"
  fi
done < "$ENV_FILE"

# Set all secrets at once
if [ -n "$secrets" ]; then
  echo "Setting secrets on fly.io..."
  flyctl secrets set $secrets
  echo "Secrets successfully set!"
else
  echo "No secrets found in $ENV_FILE"
fi 