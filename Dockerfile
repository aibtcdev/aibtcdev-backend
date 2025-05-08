FROM public.ecr.aws/docker/library/python:3.13

WORKDIR /usr/src/app

# Install Python dependencies
RUN pip install uv
COPY requirements.txt ./
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Install Bun
RUN curl -fsSL https://bun.sh/install | bash

# Set Bun path for this shell
ENV PATH="/root/.bun/bin:${PATH}"

# Install JS/TS dependencies efficiently
WORKDIR /usr/src/app/agent-tools-ts

# Copy only dependency files first for better caching
COPY agent-tools-ts/package.json agent-tools-ts/bun.lock ./
RUN bun install

# Now copy the rest of the code
COPY . .

WORKDIR /usr/src/app

CMD [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" ]