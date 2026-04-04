FROM python:3.11-slim

WORKDIR /app

COPY services/upload-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ /app/shared/
COPY services/upload-service/ /app/services/upload-service/

EXPOSE 8002

CMD ["uvicorn", "services.upload_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
