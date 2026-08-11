FROM python:3.12-slim
WORKDIR /app
COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY apps/api /app/apps/api
COPY workers/extraction_worker /app/workers/extraction_worker
ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.extraction_worker.extract_structured"]

