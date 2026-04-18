FROM python:3.13-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /worker
COPY worker.py /worker/worker.py

RUN pip install --no-cache-dir pyyaml==6.0.3 psycopg[binary]==3.3.3 psycopg-pool==3.3.0 psutil==6.1.1

CMD ["python", "/worker/worker.py"]
