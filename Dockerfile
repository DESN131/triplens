# Override to use another registry/mirror, e.g.
#   docker build --build-arg PYTHON_IMAGE=registry.example.com/library/python:3.12-slim .
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

# Override when a PyPI mirror is faster on your network, e.g.
#   docker build --build-arg PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple .
ARG PIP_INDEX=https://pypi.org/simple

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TRIPLENS_REGION=syd \
    TRIPLENS_CACHE=/data

WORKDIR /app

# dependencies first, so editing the app does not invalidate the pip layer
COPY requirements.txt ./
RUN pip install --no-cache-dir --index-url "${PIP_INDEX}" -r requirements.txt

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
