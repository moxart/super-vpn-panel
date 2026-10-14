FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /code
COPY requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /code/

EXPOSE 8000
CMD ["bash", "-c", "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"]
