FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY apps/api/requirements.txt /app/requirements.txt
COPY apps/api/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.txt -c requirements.lock && useradd --create-home applyos
COPY apps/__init__.py /app/apps/__init__.py
COPY apps/api /app/apps/api
COPY apps/worker /app/apps/worker
COPY packages/job_sources /app/packages/job_sources
COPY packages/matching /app/packages/matching
RUN mkdir -p /app/data && chown -R applyos:applyos /app/data
USER applyos
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "apps.api.applyos.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
