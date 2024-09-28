import socket
import struct
import argparse


# 回调函数，您可以根据需要实现
def on_start(session_name):
    print(f"Received 'start' command with session name: {session_name}")


def on_stop():
    print("Received 'stop' command")


# 发送状态消息给 master，自动使用 master 的来源地址，并添加 type 字段
def send_status_to_master(master_addr, port, status_code, msg_type):
    # 使用IPv6单播回复master状态
    with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as sock:
        packed_status = struct.pack("!ii", status_code, msg_type)  # 状态码和消息类型
        sock.sendto(packed_status, (master_addr, port))


# 处理接收到的数据包
def handle_message(data, master_addr, port, reply_port):
    # 打印接收到的原始数据
    print(f"Received raw data from {master_addr}: {data}, length: {len(data)}")

    # 确保数据至少有 4 个字节 (状态码)
    if len(data) < 4:
        print(f"Invalid message received from {master_addr}, data too short.")
        send_status_to_master(master_addr, reply_port, -1, -1)  # 错误代码，类型为 -1
        return

    # 解析状态码
    status = struct.unpack("!i", data[:4])[0]

    # 如果是“开始”消息，期望更多字节：状态码 (4字节) + 会话名字长度 (4字节) + 会话名字
    if status == 1:  # Start command
        # 确保有足够的字节来解包会话名字长度
        if len(data) < 8:
            print(
                f"Invalid start message received from {master_addr}, data too short for session name length."
            )
            send_status_to_master(master_addr, reply_port, -1, 1)  # 错误代码，类型为1
            return

        # 解析会话名字长度
        session_name_len = struct.unpack("!i", data[4:8])[0]

        # 确保会话名字长度合理，并且有足够的字节
        if (
            session_name_len < 0
            or session_name_len > 128
            or len(data) < 8 + session_name_len
        ):
            print(f"Invalid session name length: {session_name_len} or data too short.")
            send_status_to_master(master_addr, reply_port, -1, 1)  # 错误代码，类型为1
            return

        # 解析会话名字
        session_name = struct.unpack(
            f"!{session_name_len}s", data[8 : 8 + session_name_len]
        )[0].decode("utf-8")

        # 处理“开始”命令
        on_start(session_name)
        send_status_to_master(
            master_addr, reply_port, 0, 1
        )  # 0 表示 OK，类型为1（开始）

    elif status == 2:  # Stop command
        # 停止消息只包含状态码，因此不需要进一步解包
        on_stop()
        send_status_to_master(
            master_addr, reply_port, 0, 2
        )  # 0 表示 OK，类型为2（停止）

    else:
        print(f"Unknown command received from {master_addr}: {status}")
        send_status_to_master(master_addr, reply_port, -1, -1)  # 错误代码，类型未知


# 监听组播
def listen_multicast(multicast_group, port, reply_port):
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # 绑定到所有接口的指定端口
    sock.bind(("::", port))

    # 加入组播组
    group_bin = socket.inet_pton(socket.AF_INET6, multicast_group)
    mreq = group_bin + struct.pack("I", 0)  # 0代表所有接口
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)

    print(f"Listening for multicast messages on {multicast_group}:{port}")

    while True:
        data, address = sock.recvfrom(1024)  # 接收数据和地址（包含master地址）
        master_addr = address[0]  # 从接收到的消息中获取master的IPv6地址
        print(f"Received message from {master_addr}")
        handle_message(data, master_addr, port, reply_port)


if __name__ == "__main__":
    # 使用 argparse 来解析命令行参数
    parser = argparse.ArgumentParser(
        description="Slave node for multicast communication."
    )

    # 添加参数，并给出默认值
    parser.add_argument(
        "--multicast_group",
        type=str,
        default="ff02:ca11:4514:1919::",
        help="Multicast group address (default: ff02:ca11:4514:1919::)",
    )
    parser.add_argument(
        "--port", type=int, default=4329, help="Port to listen on (default: 4329)"
    )
    parser.add_argument(
        "--reply_port",
        type=int,
        default=4328,
        help="Port to send replies to (default: 4328)",
    )

    args = parser.parse_args()

    # 使用解析得到的参数
    multicast_group = args.multicast_group  # 组播地址
    port = args.port  # 监听的端口
    reply_port = args.reply_port  # 回复端口

    # 启动监听
    listen_multicast(multicast_group, port, reply_port)
