FROM python:3.11-slim

WORKDIR /app

# Зависимости устанавливаем отдельным слоем для кэширования
COPY services/auth-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY shared/ /app/shared/
COPY services/auth-service/ /app/services/auth-service/

EXPOSE 8001

CMD ["uvicorn", "services.auth_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
