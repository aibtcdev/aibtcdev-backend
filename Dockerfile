FROM python:3.10.15

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN curl -fsSL https://bun.sh/install | bash
RUN cp /root/.bun/bin/bun /usr/local/bin/bun
RUN cd /usr/src/app/agent-tools-ts/ && bun install

CMD [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" ]