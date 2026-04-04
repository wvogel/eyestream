FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /worker
COPY worker.py /worker/worker.py

RUN pip install --no-cache-dir pyyaml==6.0.2 psycopg[binary]==3.2.6 psycopg-pool==3.2.6 psutil==6.1.1

CMD ["python", "/worker/worker.py"]
