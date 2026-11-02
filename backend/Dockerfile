FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN groupadd --system windscope && useradd --system --gid windscope --home-dir /app windscope
COPY --chown=windscope:windscope backend/app /app/app
COPY --chown=windscope:windscope backend/snapshots /app/snapshots
ENV SNAPSHOT_REQUIRED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER windscope
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

