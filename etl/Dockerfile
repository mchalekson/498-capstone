FROM python:3.11-slim

WORKDIR /app

COPY etl/requirements.txt etl/requirements.txt
RUN pip install --no-cache-dir -r etl/requirements.txt

COPY etl/ etl/

WORKDIR /app/etl
CMD ["python", "run_all.py"]
