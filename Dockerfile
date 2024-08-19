###########################################################################################
# This Dockerfile runs an LMC-compatible websocket server at / on port 8000.              #
# To learn more about LMC, visit https://docs.openinterpreter.com/protocols/lmc-messages. #
###########################################################################################

# FROM python:3.11.8

# # Set environment variables
# # ENV OPENAI_API_KEY ...

# ENV HOST 0.0.0.0
# # ^ Sets the server host to 0.0.0.0, Required for the server to be accessible outside the container

# # Copy required files into container
# RUN mkdir -p interpreter scripts
# COPY interpreter/ interpreter/
# COPY scripts/ scripts/
# COPY poetry.lock pyproject.toml README.md ./

# # Expose port 8000
# EXPOSE 8000

# # Install server dependencies
# RUN pip install ".[server]"

# # Start the server
# ENTRYPOINT ["interpreter", "--server"]

# base image
FROM python:3.10-slim-bookworm AS base

WORKDIR /app/server

# Install Poetry
ENV POETRY_VERSION=1.8.3
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

# Configure Poetry
ENV POETRY_CACHE_DIR=/tmp/poetry_cache
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_VIRTUALENVS_CREATE=true
ENV POETRY_REQUESTS_TIMEOUT=15

FROM base AS packages

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ libc-dev libffi-dev libgmp-dev libmpfr-dev libmpc-dev

# Install Python dependencies
COPY dev/pyproject.toml dev/poetry.lock ./
RUN poetry install --extras shuling --sync --no-cache --no-root

# production stage
FROM base AS production

ENV FASTAPI_APP=app.py
ENV SERVICE_API_URL=http://127.0.0.1:8090

EXPOSE 8090

# set timezone
ENV TZ=UTC

WORKDIR /app/server

# Copy Python environment and packages
ENV VIRTUAL_ENV=/app/server/.venv
COPY --from=packages ${VIRTUAL_ENV} ${VIRTUAL_ENV}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"


# Copy source code
COPY . /app/server/

COPY dev/entrypoint.sh /entrypoint.sh
# Copy entrypoint
RUN chmod +x /entrypoint.sh


ARG COMMIT_SHA
ENV COMMIT_SHA=${COMMIT_SHA}

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]