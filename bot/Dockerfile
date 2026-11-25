FROM python:3.12-alpine
RUN pip install --no-cache-dir requests
COPY bot.py /app/bot.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/bot.py"]
