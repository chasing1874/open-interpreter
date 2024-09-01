#!/bin/bash

set -e

export PYTHONPATH=/app/server

if [[ "${DEBUG}" == "true" ]]; then
  exec uvicorn dev.llm_server:app --host ${SERVER_BIND_ADDRESS:-0.0.0.0} --port ${SERVER_PORT:-8090} --reload
else
  exec uvicorn dev.llm_server:app --host ${SERVER_BIND_ADDRESS:-0.0.0.0} --port ${SERVER_PORT:-8090}
fi