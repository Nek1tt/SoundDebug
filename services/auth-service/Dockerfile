FROM python:3.11-slim
 
WORKDIR /app
 
COPY services/auth-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
 
COPY shared/ /app/shared/
COPY services/auth-service/main.py /app/main.py
 
EXPOSE 8001
 
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]