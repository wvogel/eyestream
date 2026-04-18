FROM python:3.14-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py db.py helpers.py /app/
COPY routes /app/routes
COPY i18n /app/i18n
COPY templates /app/templates
COPY static /app/static

EXPOSE 80
CMD ["python", "/app/main.py"]
