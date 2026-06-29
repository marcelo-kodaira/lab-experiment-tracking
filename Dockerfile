FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY labtrack ./labtrack
RUN pip install --no-cache-dir .
COPY alembic.ini ./
COPY alembic ./alembic
CMD ["sh", "-c", "alembic upgrade head && python -m labtrack.seed"]
