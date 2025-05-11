FROM oven/bun:latest AS bun

# First stage: build the application with uv
FROM public.ecr.aws/docker/library/python:3.13 AS builder

# Enable bytecode compilation and set link mode
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Disable Python downloads to use the system interpreter across both images
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /usr/src/app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using the lockfile
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Copy the rest of the code
COPY . /usr/src/app

# Sync again to install the project and all dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Second stage: final image without uv
FROM public.ecr.aws/docker/library/python:3.13

# Copy the application from the builder
COPY --from=builder /usr/src/app /usr/src/app
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
COPY --from=builder /usr/src/app/agent-tools-ts/package.json /usr/src/app/agent-tools-ts/bun.lock ./

# Install JS/TS dependencies
WORKDIR /usr/src/app/agent-tools-ts
RUN bun install --frozen-lockfile

# Return to app directory
WORKDIR /usr/src/app

# Place executables in the environment at the front of the path
ENV PATH="/usr/src/app/.venv/bin:$PATH"

# Run using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]