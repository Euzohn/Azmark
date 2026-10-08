# syntax=docker/dockerfile:1.6
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
# 依赖层通过 BuildKit 缓存复用；只有 requirements.txt 变化时才重装。
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
