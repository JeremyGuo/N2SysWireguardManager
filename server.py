#!/usr/bin/env python3
import os
import subprocess
import logging
from flask import Flask, request, jsonify

app = Flask(__name__)

# Read Key from `./key`
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
logger = logging.getLogger("WireGuardServer")
# Set logger file to `server.log`
fh = logging.FileHandler('server.log')
fh.setLevel(logging.INFO)
logger.addHandler(fh)

# 全局变量：master 信息和 slave 列表
master_info = None
slave_infos = []

# IP 分配相关（示例中使用 10.0.0.0/24 网段）
MASTER_IP = "10.11.12.1"
next_slave_ip = 2

def ip_from_index(index):
    """生成 IP 地址，假定网段 10.11.12.0/24"""
    return f"10.11.12.{index}"

def generate_keypair():
    """使用 wg genkey 和 wg pubkey 生成密钥对"""
    try:
        private_key = subprocess.run(["wg", "genkey"], capture_output=True, text=True, check=True).stdout.strip()
        public_key = subprocess.run(["wg", "pubkey"], input=private_key, capture_output=True, text=True, check=True).stdout.strip()
        return private_key, public_key
    except Exception as e:
        logger.error(f"生成密钥对失败：{e}")
        return None, None

@app.route("/register", methods=["POST"])
def register():
    """
    接收 service 的注册请求，JSON 数据格式示例：
      master：
        {
          "role": "master",
          "interface": "wg0"   # 可选，默认为 wg0
        }
      slave：
        {
          "role": "slave",
          "interface": "wg1"   # 可选，默认为 wg0
        }
    注意：server 会为每个注册的 service 分配唯一的 IP 地址，
    并调用 wg genkey/wg pubkey 生成密钥对，将生成的 PrivateKey 和 PublicKey 返回给 service。
    """
    global master_info, slave_infos, next_slave_ip, key
    data = request.get_json()
    if not data or "role" not in data:
        return jsonify({"error": "注册数据不完整"}), 400
    if not "key" in data or data["key"] != key:
        return jsonify({"error": "Key 不匹配"}), 403

    role = data["role"]
    data.setdefault("interface", "wg0")
    # 生成密钥对
    private_key, public_key = generate_keypair()
    if not private_key or not public_key:
        return jsonify({"error": "密钥生成失败"}), 500

    data["private_key"] = private_key
    data["public_key"] = public_key

    if role == "master":
        # master 固定分配 MASTER_IP
        data["ip"] = MASTER_IP
        master_info = data
        logger.info(f"注册 master：{master_info}")
    elif role == "slave":
        # 检查是否已存在该 slave，若存在则更新；否则分配新 IP
        exists = False
        for i, s in enumerate(slave_infos):
            if s.get("interface") == data.get("interface"):
                exists = True
                # 保持原有 IP，不重复分配
                data["ip"] = s.get("ip")
                slave_infos[i] = data
                break
        if not exists:
            data["ip"] = ip_from_index(next_slave_ip)
            next_slave_ip += 1
            slave_infos.append(data)
        logger.info(f"注册 slave：{data}")
    else:
        return jsonify({"error": "未知的 role 类型"}), 400

    # 返回注册成功信息，包括分配的 IP 与生成的密钥对
    return jsonify({
        "status": "注册成功",
        "assigned_ip": data.get("ip"),
        "private_key": private_key,
        "public_key": public_key
    }), 200

@app.route("/sync", methods=["GET"])
def sync():
    """
    根据查询参数返回对应的配置文件内容：
      请求参数：
        - role：master 或 slave
        - public_key：请求方的公钥（由注册返回）
        - interface：接口名称，默认 wg0
    返回内容为配置文件内容文本，配置中包含：
      - Interface 部分写入 PrivateKey（直接写入，不作为注释）
      - Peer 部分包含 PersistentKeepAlive 配置（示例值为 25）
    """
    role = request.args.get("role")
    public_key = request.args.get("public_key")
    interface = request.args.get("interface", "wg0")
    global key
    arg_key = request.args.get("key")

    if role not in ("master", "slave"):
        return jsonify({"error": "unkonwn role"}), 400
    if not arg_key or arg_key != key:
        return jsonify({"error": "Key unmatch"}), 403

    config_lines = []
    persistent_keepalive = "PersistentKeepAlive = 25"

    if role == "master":
        if master_info is None or master_info.get("public_key") != public_key:
            return jsonify({"error": "master not match or registered"}), 400
        # 构造 master 配置，包含自己的 PrivateKey 与所有 slave 的 Peer 信息
        config_lines.append("[Interface]")
        config_lines.append(f"PrivateKey = {master_info.get('private_key')}")
        config_lines.append(f"MTU = 1420")
        config_lines.append(f"Address = {master_info.get('ip')}")
        config_lines.append("")
        for slave in slave_infos:
            config_lines.append("[Peer]")
            config_lines.append(f"PublicKey = {slave.get('public_key')}")
            # master 不直接访问 slave，不设置 Endpoint，但可备注 keepalive 配置
            config_lines.append(f"{persistent_keepalive}")
            config_lines.append(f"AllowedIPs = 10.11.12.0/24")
            config_lines.append("")
    elif role == "slave":
        # 查找该 slave 信息
        target = None
        for slave in slave_infos:
            if slave.get("public_key") == public_key and slave.get("interface", "wg0") == interface:
                target = slave
                break
        if target is None:
            return jsonify({"error": "slave 信息未注册"}), 400

        config_lines.append("[Interface]")
        config_lines.append(f"PrivateKey = {target.get('private_key')}")
        config_lines.append(f"MTU = 1420")
        config_lines.append(f"Address = {target.get('ip')}")
        config_lines.append("")
        # 配置 master 信息作为 Peer
        if master_info:
            config_lines.append("[Peer]")
            config_lines.append(f"PublicKey = {master_info.get('public_key')}")
            config_lines.append(f"Endpoint = {master_info.get('ip')}")
            config_lines.append(f"AllowedIPs = 10.11.12.0/24")
            config_lines.append(f"{persistent_keepalive}")
            config_lines.append("")
        else:
            config_lines.append("# master 尚未注册，暂不配置")
    config_content = "\n".join(config_lines)
    return jsonify({"config": config_content}), 200

if __name__ == "__main__":
    # 监听所有网卡，端口可根据需要调整
    app.run(host="127.0.0.1", port=8881)