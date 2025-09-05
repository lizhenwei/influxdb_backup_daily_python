# 使用官方的uv镜像作为构建阶段
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# 设置工作目录
WORKDIR /app

# 复制项目定义文件
COPY pyproject.toml uv.lock ./

# 安装项目依赖
RUN uv sync --locked

# 复制脚本文件
COPY main.py .

# 第二阶段：运行阶段
FROM python:3.12.9-slim

# 安装InfluxDB CLI (版本更新至2.7.5)
# 针对容器使用的sources.list.d/debian.sources格式进行源替换
RUN chmod 1777 /tmp && \
    # 替换deb.debian.org为阿里云镜像源
    sed -i 's|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|http://deb.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update --allow-releaseinfo-change -y && \    
    apt-get install -y --no-install-recommends wget curl && \
    wget -q https://dl.influxdata.com/influxdb/releases/influxdb2-client-2.7.5-linux-amd64.tar.gz && \
    tar xvzf influxdb2-client-2.7.5-linux-amd64.tar.gz && \
    cp ./influx /usr/local/bin/ && \
    chmod +x /usr/local/bin/influx && \
    rm -rf influxdb2-client-2.7.5-linux-amd64* && \
    apt-get purge -y --auto-remove wget curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 从构建阶段复制虚拟环境
COPY --from=builder /app/.venv /app/.venv

# 将虚拟环境添加到PATH
ENV PATH="/app/.venv/bin:$PATH"

# 复制脚本文件
COPY main.py .

# 创建日志目录
RUN mkdir -p /var/log/influxdb_backup

# 设置环境变量默认值
ENV START_DATE=""
ENV SKIP_WRITE="false"

# 设置命令入口点
CMD ["python", "main.py"]
