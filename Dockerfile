FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock

COPY . .

EXPOSE 8000 8501

CMD ["python", "-m", "uvicorn", "flood_command_center.main:app", "--host", "0.0.0.0", "--port", "8000"]
