# Wireguard Manager

本项目提供了一种非常精简的用于管理Wiregurad的方法。

场景是：
0. 一台server，所有机器可以访问（带宽受限）
1. 一台master机器，其他机器可以通过UDP访问（带宽不限）
2. 若干slave机器

希望在master和slave之间组建VPN。

组件分为两个部分：
1. server：运行在server上，负责管理网络中的机器。
2. service：运行在master和slave上，负责从master同步配置文件。

## 部署server

1. 修改并复制`n2sys_wg_server.service`到`/etc/systemd/system/`下。
2. 创建`key`文件，并写入一串随机字符串
3. 运行`systemctl daemon-reload && systemctl enable --now n2sys_wg_server`启动服务，服务运行在端口8881。
4. Optional: 用`nginx`做一个反向代理+SSL保证安全。

## 部署service

1. 安装wireguard。
2. `sudo pip install requests`。
3. `sudo python3 deploy.py --server=server.n2sys.cn --port=8801 --role=slave --endpoint=traffic.n2sys.cn --endpoint-port=23128`。
4. 创建`key`文件，写入和server的key同样的字符串。
5. 执行`sudo systemctl daemon-reload && sudo systemctl enable --now n2sys_wg`。

此时每个slave可以和master通信（不能slave互相通信），master的IP为`10.11.12.1`，slave根据hostname自动分配。
