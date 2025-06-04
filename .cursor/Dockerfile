FROM public.ecr.aws/docker/library/python:3.13

# Set environment variables for optimal Python and uv behavior
ENV UV_COMPILE_BYTECODE=1 
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    build-essential \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager)
RUN pip install uv

# Install Bun (JavaScript/TypeScript runtime)
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:$PATH"

# Install Node.js (fallback for any npm dependencies)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Create a non-root user for better security
RUN useradd -m -s /bin/bash cursor
USER cursor

# Set working directory to user's home directory
WORKDIR /home/cursor

# Set up environment for the cursor user
ENV PATH="/home/cursor/.local/bin:/home/cursor/.bun/bin:$PATH"

# Install uv for the cursor user
RUN pip install --user uv

# Pre-install common Python packages to speed up subsequent installs
# This creates a base layer that can be cached
RUN uv venv /home/cursor/.venv
ENV PATH="/home/cursor/.venv/bin:$PATH"

# Pre-install some common dependencies to create a warmer cache
RUN uv pip install \
    fastapi \
    uvicorn \
    pydantic \
    sqlalchemy \
    requests \
    openai \
    langchain

# Set default shell to bash for better compatibility
SHELL ["/bin/bash", "-c"]

# Create directory structure that the project expects
RUN mkdir -p /home/cursor/workspace

CMD ["/bin/bash"]
