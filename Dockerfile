FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TRIPLENS_REGION=syd \
    TRIPLENS_CACHE=/data

WORKDIR /app

# dependencies first, so editing the app does not invalidate the pip layer
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py ./

# run unprivileged; /data keeps the downloaded timetable files between restarts
RUN useradd --create-home --uid 10001 triplens \
 && mkdir -p /data \
 && chown -R triplens:triplens /app /data
USER triplens

EXPOSE 8090
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD python -c "import sys,urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:8090/api/meta', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
