FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY src/ src/

RUN mkdir -p embeddings && \
    mkdir -p /home/nobody/.cache/huggingface && \
    chown -R nobody:nogroup /app /home/nobody && \
    chmod -R 755 /app /home/nobody

ENV PYTHONPATH=/app
ENV HOME=/home/nobody

USER nobody

EXPOSE 8000

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
