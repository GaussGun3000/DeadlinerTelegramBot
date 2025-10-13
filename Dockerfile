FROM python:3.11-slim

# system deps (optional but useful)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy source
COPY . .

# env
ENV PYTHONUNBUFFERED=1

# run
CMD ["python", "-u", "main.py"]
