FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 eduagent \
    && mkdir -p /app/data \
    && chown -R eduagent:eduagent /app

USER eduagent

EXPOSE 8888

CMD ["python", "-m", "api.main"]
