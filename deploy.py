import argparse
import subprocess

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

    cur_workdir = os.getcwd()
    exec_cmd = cur_workdir + "/service.py"
    exec_cmd += " --server " + args.server
    exec_cmd += " --port " + str(args.port)
    exec_cmd += " --role " + args.role
    exec_cmd += " --interface " + args.interface
    exec_cmd += " --interval " + str(args.interval)
    if args.endpoint:
        exec_cmd += " --endpoint " + args.endpoint
        exec_cmd += " --endpoint-port " + str(args.endpoint_port)
    
    #Read template n2sys_wg.service
    service_template
    with open("n2sys_wg.service", "r") as f:
        service_template = f.read()
    service_template.replace("@A", exec_cmd)

    #Write to /etc/systemd/system/n2sys_wg.service
    with open("/etc/systemd/system/n2sys_wg.service", "w") as f:
        f.write(service_template)
