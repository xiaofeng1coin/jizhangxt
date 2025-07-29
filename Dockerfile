# 文件路径: Dockerfile

# ---- STAGE 1: Builder (安装依赖) ----
FROM python:3.11-slim-bookworm as builder
WORKDIR /app
RUN pip install --upgrade pip

# 从 app/ 目录复制 requirements.txt
COPY requirements.txt .

# 将依赖安装到一个特定目录，方便下一阶段复制
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- STAGE 2: Final Image (最终运行环境) ----
FROM python:3.11-slim-bookworm

# ----------------- 时区设置 -----------------
ENV TZ=Asia/Shanghai
RUN set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*
# --------------------------------------------------------

WORKDIR /app

# 从 builder 阶段复制已经安装好的依赖
COPY --from=builder /install /usr/local

# 从 根目录复制所有代码 (包括 app.py, static/, templates/)
COPY . .

# 暴露 Flask 应用运行的端口
EXPOSE 5000

# 设置环境变量，确保 Python 日志直接输出
ENV PYTHONUNBUFFERED=1

# 使用 'python' 命令来直接启动 'app.py'。
CMD ["python", "app.py"]
