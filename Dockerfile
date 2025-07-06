# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /kc_app

# Add these for psycopg2 build
RUN apt-get update && apt-get install -y \
    libpq-dev gcc

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

CMD gunicorn oaklab.wsgi:application --bind 0.0.0.0:$PORT