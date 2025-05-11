FROM public.ecr.aws/docker/library/python:3.13

WORKDIR /usr/src/app

RUN pip install uv

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Install Bun
RUN curl -fsSL https://bun.sh/install | bash

# Set Bun path for this shell
ENV PATH="/root/.bun/bin:${PATH}"

# Install JS/TS dependencies efficiently
WORKDIR /usr/src/app/agent-tools-ts

# Copy only dependency files first for better caching
COPY agent-tools-ts/package.json agent-tools-ts/bun.lock ./
RUN bun install --frozen-lockfile

# Now copy the rest of the code
WORKDIR /usr/src/app
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT [ "uv", "run" ]

CMD [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" ]