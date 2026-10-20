FROM python:3.11-slim

ARG PIP_INDEX_URL=https://pypi.org/simple

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_PROGRESS_BAR=off

COPY requirements.txt .
# 依赖层通过 BuildKit 缓存复用；只有 requirements.txt 变化时才重装。
# PIP_INDEX_URL 由 compose 传入，服务器网络慢时可切换镜像源。
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --index-url "$PIP_INDEX_URL" --prefer-binary -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
