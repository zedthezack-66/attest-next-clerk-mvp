FROM python:3.12-slim
WORKDIR /app
COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY apps/api /app/apps/api
COPY packages/db-schema /app/packages/db-schema
ENV PYTHONPATH=/app
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

