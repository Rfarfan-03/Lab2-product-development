FROM python:3.11.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY docker/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY novamercado/ /app/novamercado/

EXPOSE 8000

CMD ["uvicorn", "novamercado.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
