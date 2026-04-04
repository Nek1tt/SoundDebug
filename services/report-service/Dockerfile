FROM python:3.11-slim

WORKDIR /app

COPY services/report-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ /app/shared/
COPY services/report-service/ /app/services/report-service/

EXPOSE 8003

CMD ["uvicorn", "services.report_service.main:app", "--host", "0.0.0.0", "--port", "8003"]
