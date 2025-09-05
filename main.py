#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import paramiko
import os
import logging
import datetime
import subprocess
import sys
import requests
import json

# 固定参数配置
HOST = 'your_server_ip'  # 请替换为实际的服务器IP地址
PORT = 22  # 请替换为实际的SSH端口
USERNAME = 'your_username'  # 请替换为实际的SSH用户名
PASSWORD = 'your_password'  # 请替换为实际的SSH密码
KEY_FILENAME = None  # 如果使用密钥认证，可以设置私钥文件路径
BUCKET_ID = 'your_bucket_id'  # 请替换为实际的bucket ID
ENGINE_PATH = '/path/to/influxdb/engine/'  # 请替换为实际的InfluxDB引擎路径
REMOTE_BACKUP_DIR = '/path/to/remote/backup'  # 请替换为实际的远程备份目录
LOCAL_BACKUP_DIR = '/path/to/local/backup'  # 请替换为实际的本地备份目录

# InfluxDB写入配置参数
INFLUXDB_HOST = 'http://your_influxdb_server:8086'  # 请替换为实际的InfluxDB服务器地址
INFLUXDB_ORG = 'your_organization'  # 请替换为实际的组织名称
INFLUXDB_TOKEN = 'your_api_token'  # 请替换为实际的API令牌
TARGET_BUCKET = 'target_bucket_name'  # 请替换为实际的目标bucket名称

# 企业微信通知配置
WECHAT_WEBHOOK_URL = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_webhook_key'  # 请替换为实际的企业微信Webhook URL

def send_wechat_notification(error_message):
    """发送企业微信通知"""
    try:
        # 构建消息体
        message = {
            "msgtype": "text",
            "text": {
                "content": f"⚠️ InfluxDB江阴每日备份程序异常\n" \
                           f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
                           f"错误信息: {error_message}"
            }
        }
        
        # 发送请求
        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            WECHAT_WEBHOOK_URL,
            data=json.dumps(message),
            headers=headers,
            timeout=10
        )
        
        # 检查响应
        if response.status_code == 200:
            result = response.json()
            if result.get('errcode') == 0:
                logger.info("企业微信通知发送成功")
            else:
                logger.warning(f"企业微信通知发送失败: {result}")
        else:
            logger.warning(f"企业微信通知发送失败，HTTP状态码: {response.status_code}")
    except Exception as e:
        logger.warning(f"发送企业微信通知时发生异常: {str(e)}")

# 配置日志
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('./influx_export_download.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

# 创建SSH连接
def create_ssh_connection(hostname, port, username, password=None, key_filename=None):
    """创建并返回SSH连接对象"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            key_filename=key_filename,
            timeout=30
        )
        # 设置SSH心跳，每30秒发送一次心跳包保持连接活跃
        transport = ssh.get_transport()
        if transport:
            transport.set_keepalive(30)
        logger.info(f"成功连接到服务器: {hostname}:{port}，已设置心跳每30秒")
        return ssh
    except Exception as e:
        logger.error(f"连接服务器失败: {str(e)}")
        raise

# 执行远程命令
def execute_remote_command(ssh, command):
    """在远程服务器上执行命令并返回结果"""
    logger.info(f"执行远程命令: {command}")
    stdin, stdout, stderr = ssh.exec_command(command)
    
    # 获取命令执行结果
    exit_code = stdout.channel.recv_exit_status()
    output = stdout.read().decode('utf-8')
    error = stderr.read().decode('utf-8')
    
    if exit_code != 0:
        logger.error(f"命令执行失败: {error}")
        raise Exception(f"命令执行失败，退出码: {exit_code}, 错误: {error}")
    
    logger.info(f"命令执行成功: {output}")
    return output

# 下载文件
def download_file(ssh, remote_path, local_path):
    """从远程服务器下载文件到本地，显示下载进度"""
    try:
        sftp = ssh.open_sftp()
        logger.info(f"开始下载文件: {remote_path} -> {local_path}")
        
        # 获取远程文件大小
        remote_file_size = sftp.stat(remote_path).st_size
        logger.info(f"远程文件大小: {remote_file_size} 字节")
        
        # 定义下载进度回调函数
        def callback(transferred, total):
            progress = (transferred / total) * 100
            # 每5%进度或文件较小时更频繁地更新进度
            if progress % 5 < 0.5 or total < 1024 * 1024:  # 小于1MB的文件更频繁显示
                logger.info(f"下载进度: {transferred}/{total} 字节 ({progress:.1f}%)")
        
        # 使用回调函数下载文件
        sftp.get(remote_path, local_path, callback=callback)
        sftp.close()
        logger.info(f"文件下载成功: {local_path}")
        # 打印最终文件大小
        file_size = os.path.getsize(local_path)
        logger.info(f"文件大小: {file_size} 字节")
    except Exception as e:
        logger.error(f"文件下载失败: {str(e)}")
        raise

# 检查InfluxDB bucket中的数据总量
def check_influxdb_data_count(bucket, org, token, host, start_date, end_date, measurement="ess_telemetry_t"):
    """检查InfluxDB bucket中指定measurement的数据总量并返回计数值"""
    try:
        logger.info(f"开始检查InfluxDB bucket '{bucket}' 中 '{measurement}' 的数据总量，时间范围: {start_date} 到 {end_date}")
        
        # 构建Flux查询语句，使用传入的start_date和end_date
        flux_query = (
            f'from(bucket: "{bucket}") ' \
            f'|> range(start: {start_date}T00:00:00Z, stop: {end_date}T00:00:00Z) ' \
            f'|> filter(fn: (r) => r["_measurement"] == "{measurement}") ' \
            f'|> count() ' \
            f'|> group(columns:["_measurement"]) ' \
            f'|> sum()'
        )
        
        # 构建influx query命令字符串
        command = (
            f"influx query "
            f"--org '{org}' "
            f"--token '{token}' "
            f"--host '{host}' "
            f"'{flux_query}'"
        )
        
        # 打印命令
        logger.info(f"执行查询命令: {command}")
        
        # 执行命令，使用shell=True
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"数据总量查询结果: {result.stdout}")
        
        # 尝试从输出中解析计数值
        try:
            # 假设输出格式为: _measurement,result,table count
            # 例如: ess_telemetry_t,,0 1000000
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines:
                # 跳过表头和空行
                if not line or line.startswith('_measurement'):
                    continue
                # 提取数字部分
                parts = line.split()
                if parts and parts[-1].isdigit():
                    count = int(parts[-1])
                    logger.info(f"解析得到数据总量: {count}")
                    return count
            logger.warning(f"无法从输出中解析计数值,返回0")
            return 0
        except Exception as parse_error:
            logger.warning(f"解析计数值时出错: {str(parse_error)}，返回原始输出")
            return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"查询数据总量失败: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"查询操作异常: {str(e)}")
        raise

# 使用influx write将文件写入到bucket
def write_to_influxdb(file_path, bucket, org, token, host):
    """使用influx write命令将备份文件写入到InfluxDB bucket中"""
    try:
        logger.info(f"开始将文件 {file_path} 写入到InfluxDB bucket {bucket}")
        
        # 先使用gzip解压文件
        uncompressed_file_path = file_path.replace('.gz', '')
        logger.info(f"开始解压文件: {file_path} -> {uncompressed_file_path}")
        
        # 执行gzip解压命令
        try:
            subprocess.run(
                ['gzip', '-d', '-c', file_path],
                check=True,
                stdout=open(uncompressed_file_path, 'wb'),
                stderr=subprocess.PIPE,
                text=False
            )
            logger.info(f"文件解压成功: {uncompressed_file_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"文件解压失败: {e.stderr}")
            raise
        
        # 构建influx write命令字符串（移除--compression gzip参数）
        command = (
            f"influx write "
            f"--bucket '{bucket}' "
            f"--org '{org}' "
            f"--token '{token}' "
            f"--host '{host}' "
            f"--file '{uncompressed_file_path}' "
            f"&& date"
        )
        
        # 打印命令
        logger.info(f"执行命令: {command}")
        
        # 执行命令，使用shell=True
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"文件成功写入InfluxDB: {result.stdout}")
        
        # 写入完成后清理临时解压文件
        try:
            import os
            if os.path.exists(uncompressed_file_path):
                os.remove(uncompressed_file_path)
                logger.info(f"临时解压文件已清理: {uncompressed_file_path}")
        except Exception as e:
            logger.warning(f"清理临时解压文件时出错: {str(e)}")
    except subprocess.CalledProcessError as e:
        logger.error(f"写入InfluxDB失败: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"写入操作异常: {str(e)}")
        raise

# 主函数
def main():
    # 从环境变量读取参数
    start_date = os.environ.get('START_DATE')
    # start_date = "2025-09-03"
    skip_write = os.environ.get('SKIP_WRITE', 'false').lower() in ('true', '1', 'yes')
    
    # 记录环境变量设置
    logger.info(f"环境变量设置: START_DATE={start_date}, SKIP_WRITE={skip_write}")
    
    # 确定开始和结束日期
    if start_date:
        # 如果用户设置了start_date，则使用设置的值
        try:
            # 验证日期格式是否正确
            start_date_obj = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
            # 结束日期为开始日期的下一天
            end_date_obj = start_date_obj + datetime.timedelta(days=1)
            end_date = end_date_obj.strftime('%Y-%m-%d')
            logger.info(f"使用用户指定的日期范围: {start_date} 到 {end_date}")
        except ValueError:
            logger.error("日期格式错误，请使用YYYY-MM-DD格式，如2025-08-29")
            sys.exit(1)
    else:
        # 如果没有设置start_date，则使用默认的昨天和今天
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        start_date = yesterday.strftime('%Y-%m-%d')
        end_date = datetime.date.today().strftime('%Y-%m-%d')
        logger.info(f"使用默认日期范围: {start_date} 到 {end_date}")
    
    # 确保本地备份目录存在
    if not os.path.exists(LOCAL_BACKUP_DIR):
        os.makedirs(LOCAL_BACKUP_DIR)
        logger.info(f"创建本地备份目录: {LOCAL_BACKUP_DIR}")
    
    # 构建导出命令和文件名
    export_filename = f"bak_{start_date}_to_{end_date}.lp.gz"
    remote_file_path = os.path.join(REMOTE_BACKUP_DIR, export_filename)
    local_file_path = os.path.join(LOCAL_BACKUP_DIR, export_filename)
    
    # 构建influxd导出命令
    export_command = f"""
    sudo influxd inspect export-lp \
      --bucket-id {BUCKET_ID} \
      --engine-path {ENGINE_PATH} \
      --output-path {remote_file_path} \
      --start {start_date}T00:00:00Z \
      --end {end_date}T00:00:00Z \
      --compress && date
    """
    
    try:
        # 创建SSH连接
        with create_ssh_connection(
            HOST, PORT, USERNAME, PASSWORD, KEY_FILENAME
        ) as ssh:
            # 确保远程备份目录存在
            execute_remote_command(ssh, f"mkdir -p {REMOTE_BACKUP_DIR}")
            
            # 执行导出命令
            execute_remote_command(ssh, export_command)
            
            # 下载文件
            download_file(ssh, remote_file_path, local_file_path)
            
            logger.info("导出和下载操作完成!")
            logger.info(f"文件已保存到: {local_file_path}")
            time.sleep(1)
            # 将下载的文件写入到InfluxDB bucket
            if not skip_write:
                logger.info("开始执行写入InfluxDB操作...")
                # 检查必要的InfluxDB配置参数是否已设置
                if INFLUXDB_ORG == 'your_organization' or INFLUXDB_TOKEN == 'your_api_token' or TARGET_BUCKET == 'target_bucket_name':
                    logger.warning("InfluxDB配置参数尚未设置，请先修改脚本中的INFLUXDB_ORG、INFLUXDB_TOKEN和TARGET_BUCKET参数")
                else:
                    # 在写入前检查数据总量
                    before_count = check_influxdb_data_count(
                        TARGET_BUCKET,
                        INFLUXDB_ORG,
                        INFLUXDB_TOKEN,
                        INFLUXDB_HOST,
                        start_date,
                        end_date,
                        "ess_telemetry_t"
                    )
                    
                    # 写入数据到InfluxDB
                    write_to_influxdb(
                        local_file_path,
                        TARGET_BUCKET,
                        INFLUXDB_ORG,
                        INFLUXDB_TOKEN,
                        INFLUXDB_HOST
                    )
                    
                    # 在写入后再次检查数据总量
                    logger.info("写入完成，开始检查写入后的数据总量...")
                    after_count = check_influxdb_data_count(
                        TARGET_BUCKET,
                        INFLUXDB_ORG,
                        INFLUXDB_TOKEN,
                        INFLUXDB_HOST,
                        start_date,
                        end_date,
                        "ess_telemetry_t"
                    )
                    
                    # 计算并记录数据增量
                    try:
                        if isinstance(before_count, int) and isinstance(after_count, int):
                            increment = after_count - before_count
                            logger.info(f"数据总量统计: 写入前={before_count}, 写入后={after_count}, 新增数据量={increment}")
                        else:
                            logger.info(f"无法计算精确增量，写入前结果={before_count}，写入后结果={after_count}")
                    except Exception as calc_error:
                        logger.warning(f"计算数据增量时出错: {str(calc_error)}")
                    
                    logger.info("所有操作完成!")
            else:
                logger.info("已跳过写入InfluxDB操作")
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"操作失败: {error_msg}")
        # 发送企业微信通知
        send_wechat_notification(error_msg)
        sys.exit(1)

# 全局logger变量，供send_wechat_notification函数使用
logger = None

if __name__ == "__main__":
    logger = setup_logging()
    main()
