FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py config.py ./
COPY src/ src/
COPY scripts/ scripts/

ENV PYTHONUNBUFFERED=1
ENV AUTO_CONFIRM=true

CMD ["python", "main.py"]
