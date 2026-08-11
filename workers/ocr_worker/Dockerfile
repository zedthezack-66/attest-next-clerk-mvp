FROM python:3.12-slim
WORKDIR /app
COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt pypdf==4.3.1 python-docx==1.1.2 pillow==10.4.0
COPY apps/api /app/apps/api
COPY workers/ocr_worker /app/workers/ocr_worker
ENV PYTHONPATH=/app
CMD ["python", "-m", "workers.ocr_worker.extract_text"]

