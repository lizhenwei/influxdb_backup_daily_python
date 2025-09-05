# InfluxDB每日备份恢复程序

## 项目概述

这是一个用于InfluxDB数据库每日备份和恢复的自动化工具，主要功能是通过SSH连接远程InfluxDB服务器，执行数据导出，下载备份文件，并将数据写入到目标InfluxDB实例。相比之前的shll方式,换了influxd inspect export-lp方法来备份,使用influx write方法来写入,速度更快

## 功能特性

- ✅ 通过SSH远程连接InfluxDB服务器
- ✅ 执行InfluxDB数据导出命令
- ✅ 文件下载进度显示
- ✅ 支持数据写入目标InfluxDB实例
- ✅ 企业微信异常通知
- ✅ Docker容器化部署支持
- ✅ 可配置日期范围导出
- ✅ 支持跳过写入操作

## 环境要求

- Python 3.12+ 或 Docker
- InfluxDB CLI 工具
- SSH连接权限
- 网络连接（企业微信通知功能）

## 本地安装

### 1. 克隆代码仓库

```bash
git clone https://github.com/lizhenwei/influxdb_backup_daily_python
cd influxdb_backup_daily
```

### 2. 安装依赖

```bash
# 使用pip安装依赖
pip install -r requirements.txt

# 或使用uv（如项目中已配置）
uv sync
```

### 3. 配置环境变量

程序支持通过环境变量设置以下参数：

```bash
# 设置开始日期（格式：YYYY-MM-DD），不设置则默认使用昨天
export START_DATE="2025-09-03"

# 设置是否跳过写入操作，默认为false
export SKIP_WRITE="false"
```

## 配置说明

主要配置参数位于`main.py`文件中：

```python
# SSH连接配置
HOST = 'your_remote_server_ip'        # 远程服务器地址
PORT = 22                # SSH端口
USERNAME = 'your_ssh_username'        # SSH用户名
PASSWORD = 'your_ssh_password'  # SSH密码
KEY_FILENAME = None          # SSH私钥文件路径（如果使用密钥认证）

# InfluxDB配置
BUCKET_ID = 'your_bucket_id'  # 源InfluxDB的bucket ID
ENGINE_PATH = '/path/to/influxdb/engine/'  # InfluxDB引擎路径
REMOTE_BACKUP_DIR = '/path/to/remote/backup'  # 远程备份目录
LOCAL_BACKUP_DIR = '/path/to/local/backup'   # 本地备份目录

# 目标InfluxDB配置
INFLUXDB_HOST = 'http://your_influxdb_server:8086'    # 目标InfluxDB服务器地址
INFLUXDB_ORG = 'your_organization'                    # 组织名称
INFLUXDB_TOKEN = 'your_influxdb_token'  # API令牌
TARGET_BUCKET = 'your_target_bucket'                        # 目标bucket名称

# 企业微信通知配置
WECHAT_WEBHOOK_URL = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_wechat_key'
```

## 使用方法

### 本地运行

```bash
# 直接运行主程序
python main.py

# 或使用chmod +x后直接执行
chmod +x main.py
./main.py
```



## Docker部署

### 1. 构建Docker镜像

```bash
docker build -t influxdb_backup_daily .
```

### 2. 运行Docker容器

```bash
docker run -d \
  --name influxdb_backup \
  -e START_DATE="2025-09-03" \
  -e SKIP_WRITE="false" \
  -v /path/to/backup:/mnt/datadisk0/backup \
  influxdb_backup_daily
```

### 3. 使用Docker Compose

创建`docker-compose.yml`文件：

```yaml
version: '3'

services:
  influxdb_backup:
    build: .
    container_name: influxdb_backup
    environment:
      - START_DATE=2025-09-03
      - SKIP_WRITE=false
    volumes:
      - /path/to/backup:/mnt/datadisk0/backup
    restart: always
```

启动服务：

```bash
docker-compose up -d
```

## 日志说明

程序生成两种日志：

1. `influx_export_download.log` - 记录程序执行过程的详细日志
2. `cron.log` - 记录cron定时任务执行的日志

## 常见问题

### SSH连接失败

- 检查主机地址、端口、用户名和密码是否正确
- 确保远程服务器已允许SSH连接
- 如使用密钥认证，检查密钥文件路径和权限

### InfluxDB导出失败

- 确认InfluxDB服务运行正常
- 检查bucket ID是否正确
- 验证引擎路径和备份目录是否存在且有写权限

### 企业微信通知未收到

- 检查webhook URL是否正确
- 确认企业微信应用权限配置正确

## 项目结构

```
├── main.py              # 主程序文件
├── requirements.txt     # Python依赖清单
├── Dockerfile           # Docker构建文件
├── run_influx_write.sh  # InfluxDB写入脚本
├── .gitignore           # Git忽略文件
├── .dockerignore        # Docker忽略文件
├── pyproject.toml       # Python项目配置
├── uv.lock              # UV依赖锁定文件
└── README.md            # 项目说明文档
```

## 注意事项

1. 本程序包含敏感信息（如密码、令牌等），请妥善保管
2. 建议定期检查备份文件和日志，确保备份恢复过程正常
3. 如需修改目标InfluxDB或企业微信配置，请更新相应参数
4. 在生产环境使用前，建议先在测试环境验证功能
