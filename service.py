#!/usr/bin/env python3
import argparse
import logging
import requests
import time
import subprocess
import os
import json

key = None
with open("./key", "r") as f:
    key = f.read().strip()
if not key:
    raise Exception("Key not found")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("WireGuardService")
# write log to service.log
fh = logging.FileHandler('service.log')
fh.setLevel(logging.INFO)
logger.addHandler(fh)

def register_service(server_url, role, endpoint=None):
    global key
    hostname = subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()
    payload = {
        "role": role,
        "uid": hostname,
        "key": key
    }
    if role == "master":
        payload["endpoint"] = endpoint
    try:
        logger.info(f"向 {server_url}/register 发送注册请求: {payload}")
        response = requests.post(f"{server_url}/register", json=payload, timeout=5, verify=False)
        if response.status_code == 200:
            return True
        else:
            logger.error(f"注册失败，返回：{response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"发送注册请求时发生错误：{e}")
        return False

def fetch_and_update_config(server_url, interface):
    """
    从 server 获取最新配置内容，并写入本地配置文件，然后重启对应的 WireGuard 服务
    """
    hostname = subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()
    global key
    try:
        params = {
            "uid": hostname,
            "key": key
        }
        logger.info(f"请求同步配置: {params}")
        response = requests.get(f"{server_url}/sync", params=params, timeout=5, verify=False)
        if response.status_code == 200:
            data = response.json()
            config = data.get("config")
            if config:
                config_path = f"/etc/wireguard/{interface}.conf"
                # 如果配置内容有变化，则更新并重启服务
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        current = f.read()
                else:
                    current = ""
                if current != config:
                    logger.info("配置有更新，写入新配置")
                    with open(config_path, "w") as f:
                        f.write(config)
                    # 重启对应的 wg-quick@ 服务
                    subprocess.run(["systemctl", "restart", f"wg-quick@{interface}"], check=True)
                    logger.info(f"wg-quick@{interface} 重启成功")
                else:
                    logger.info("配置未发生变化")
            else:
                logger.error("返回数据中未包含配置内容")
        else:
            logger.error(f"同步配置失败，返回：{response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"获取或更新配置时发生错误：{e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WireGuard 配置管理 Service（长驻同步模式）")
    parser.add_argument("--server", type=str, required=True, help="Server 地址")
    parser.add_argument("--port", type=int, default=8088, help="Server 端口，默认为 8088")
    parser.add_argument("--role", type=str, choices=["master", "slave"], required=True, help="服务角色：master 或 slave")
    parser.add_argument("--interface", type=str, default="n2sys_tunnel_wg", help="WireGuard 接口名称，默认为 n2sys_tunnel_wg")
    parser.add_argument("--interval", type=int, default=60, help="同步间隔（秒），默认为 60s")
    parser.add_argument("--endpoint", type=str, help="master 服务的 endpoint")
    parser.add_argument("--endpoint-port", type=int, help="master 服务的 endpoint 端口，默认为 51820")
    args = parser.parse_args()

    server_url = f"https://{args.server}:{args.port}"

    # 注册并获取 server 分配的 public_key
    status = False
    if args.role == "master":
        status = register_service(server_url, args.role, f"{args.endpoint}:{args.endpoint_port}")
    else:
        status = register_service(server_url, args.role)
    if not status:
        logger.error("注册失败，退出")
        exit(1)
    
    if role == "slave":
        # 启动一个线程，每10秒钟发起一次ping
        def ping_thread():
            while True:
                subprocess.run(["ping", "-c", "1", args.server], check=True)
                subprocess.run(["ping", "-c", "1", args.endpoint], check=True)
                time.sleep(10)
        
        import threading
        ping_t = threading.Thread(target=ping_thread)
        pint_t.start()


    # 进入持续同步循环
    while True:
        fetch_and_update_config(server_url, args.interface)
        time.sleep(args.interval)