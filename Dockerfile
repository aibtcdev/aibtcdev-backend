# Second stage: final image without uv
FROM public.ecr.aws/docker/library/python:3.13-slim

# Install libmagic1 for mime type detection
RUN apt-get update && apt-get install -y libmagic1

# Copy the application from the builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=oven/bun:latest /usr/local/bin/bun /usr/local/bin/bun

# Copy the rest of the code
COPY . /usr/src/app

# Install JS/TS dependencies
WORKDIR /usr/src/app/agent-tools-ts
RUN bun install --frozen-lockfile

# Install Python dependencies
WORKDIR /usr/src/app
RUN uv sync --frozen --no-cache

# Place executables in the environment at the front of the path
ENV PATH="/usr/src/app/.venv/bin:$PATH"

# Run using uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]