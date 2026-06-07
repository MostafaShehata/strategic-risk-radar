#!/usr/bin/env sh
set -eu

echo "$(date -Iseconds) | MODEL | startup | starting Ollama server for model ${OLLAMA_MODEL}"

ollama serve &
SERVER_PID="$!"

echo "$(date -Iseconds) | MODEL | startup | waiting for Ollama API"
until ollama list >/dev/null 2>&1; do
  sleep 2
done
echo "$(date -Iseconds) | MODEL | startup | Ollama API is ready"

if ! ollama list | awk '{print $1}' | grep -qx "$OLLAMA_MODEL"; then
  echo "$(date -Iseconds) | MODEL | model | pulling ${OLLAMA_MODEL} into persistent volume"
  ollama pull "$OLLAMA_MODEL"
  echo "$(date -Iseconds) | MODEL | model | pull completed for ${OLLAMA_MODEL}"
else
  echo "$(date -Iseconds) | MODEL | model | ${OLLAMA_MODEL} already exists in persistent volume"
fi

echo "$(date -Iseconds) | MODEL | startup | model service ready on ${OLLAMA_HOST}"
wait "$SERVER_PID"
