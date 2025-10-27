# syntax=docker/dockerfile:1
FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir --upgrade pip
COPY custom-crd/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY custom-crd/app.py ./app.py
# kopf listens to KUBERNETES_* env in cluster; use standalone mode
ENTRYPOINT ["kopf", "run", "--standalone", "/app/app.py"]
