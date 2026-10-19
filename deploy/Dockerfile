FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-nanum && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements*.txt constraints-test.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt -c constraints-test.txt
COPY src ./src
COPY deploy/start.py ./start.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --uid 10001 --create-home spot
ENTRYPOINT ["python", "start.py"]
