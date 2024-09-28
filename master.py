import socket
import struct
import FreeSimpleGUI as sg  # 假设替换为 FreeSimpleGUI
import threading

# 全局变量
is_listening = False  # 是否在监听
sock = None  # 监听的socket


# 回调函数占位，您可以根据业务逻辑实现
def on_start(session_name):
    print(f"Starting session: {session_name}")


def on_stop():
    print("Stopping session")


# 默认的回调函数，当收到slave回复时调用
def on_slave_reply(address, status, msg_type):
    print(
        f"Received reply from {address}: Status = {status}, Message Type = {msg_type}"
    )


# 发送“开始”消息给slaves
def send_start_message(multicast_group, port, session_name):
    global sock
    session_name_len = len(session_name)
    if session_name_len > 128:
        print("Session name too long!")
        return

    # 数据包格式: 状态码 (int4), 会话名字长度 (int4), 会话名字 (str)
    status = 1
    packed_data = struct.pack(
        f"!ii{session_name_len}s",
        status,
        session_name_len,
        session_name.encode("utf-8"),
    )

    # 打印发送的数据包
    print(f"Sending packed data: {packed_data}, length: {len(packed_data)}")

    # 使用已经创建的socket发送消息
    sock.sendto(packed_data, (multicast_group, port))
    on_start(session_name)


# 发送“停止”消息给slaves
def send_stop_message(multicast_group, port):
    global sock
    status = 2
    packed_data = struct.pack("!i", status)

    # 打印发送的数据包
    print(f"Sending packed data: {packed_data}, length: {len(packed_data)}")

    # 使用已经创建的socket发送消息
    sock.sendto(packed_data, (multicast_group, port))
    on_stop()


# 接收slave回复的线程，只启动一次
def receive_slave_replies(reply_port, on_reply_callback):
    global sock
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.bind(("::", reply_port))  # 监听指定端口用于接收slave回复

    print(f"Listening for replies on port {reply_port}")

    while True:
        data, address = sock.recvfrom(1024)  # 接收来自slave的回复
        if len(data) >= 8:  # 期望收到 状态码 (4字节) 和类型字段 (4字节)
            status, msg_type = struct.unpack("!ii", data[:8])  # 解包状态码和消息类型
            on_reply_callback(address, status, msg_type)  # 调用回调函数


# 创建组播套接字（只初始化一次）
def create_multicast_socket(multicast_group, port):
    global sock
    if sock is None:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # 绑定套接字到所有接口和给定端口
        sock.bind(("::", port))

        # 设置组播接口为所有接口
        interface_index = 0  # 0表示所有接口
        group_bin = socket.inet_pton(socket.AF_INET6, multicast_group)
        mreq = group_bin + struct.pack("I", interface_index)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)


# GUI部分
def main():
    global is_listening

    # GUI布局
    layout = [
        [sg.Text("Session Name"), sg.Input(key="session_name")],
        [
            sg.Text("Multicast Address (default ff02:ca11:4514:1919::)"),
            sg.Input(default_text="ff02:ca11:4514:1919::", key="multicast_address"),
        ],
        [sg.Text("Port (default 4329)"), sg.Input(default_text="4329", key="port")],
        [
            sg.Text("Reply Port (default 4328)"),
            sg.Input(default_text="4328", key="reply_port"),
        ],
        [sg.Button("Start"), sg.Button("Stop"), sg.Button("Exit")],
    ]

    window = sg.Window("Master Control", layout)

    # 获取GUI输入
    event, values = window.read(timeout=0)
    multicast_address = values.get("multicast_address", "ff02:ca11:4514:1919::")
    port = int(values.get("port", 4329))
    reply_port = int(values.get("reply_port", 4328))

    # 启动监听线程，只启动一次
    if not is_listening:
        is_listening = True
        threading.Thread(
            target=receive_slave_replies, args=(reply_port, on_slave_reply), daemon=True
        ).start()

    # 主循环
    while True:
        event, values = window.read()

        if event == sg.WINDOW_CLOSED or event == "Exit":
            break

        session_name = values["session_name"]
        multicast_address = values["multicast_address"]
        port = int(values["port"])

        # 确保组播socket已经初始化
        create_multicast_socket(multicast_address, port)

        if event == "Start":
            send_start_message(multicast_address, port, session_name)

        elif event == "Stop":
            send_stop_message(multicast_address, port)

    window.close()


if __name__ == "__main__":
    main()
