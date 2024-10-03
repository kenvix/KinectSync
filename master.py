import socket
import struct
import time
import FreeSimpleGUI as sg  # 假设替换为 FreeSimpleGUI
import threading
from loguru import logger
import argparse
from libs import processutils

processutils.make_dpi_aware()

# 全局变量
is_listening = False  # 是否在监听
sock = None  # 监听的socket
recording_processes = []  # 记录所有设备的进程
listen_thread = None  # 用于保存监听线程
start_time = time.perf_counter()

# 回调函数占位，您可以根据业务逻辑实现
def on_start(session_name):
    logger.info(f"Starting session: {session_name}")

def on_stop():
    logger.info("Stopping session")

# 默认的回调函数，当收到slave回复时调用
def on_slave_reply(address, status, msg_type, msg_length, msg_text):
    logger.info(
        f"Received reply from {address}: Status = {status}, Message Type = {msg_type}"
    )

    # 如果消息长度不为 0，表示有错误信息或状态信息
    if msg_length > 0:
        logger.info(f"Message from {address}: {msg_text}")
        if status < 0:
            logger.warning(f"Slave {address} reported an error: {msg_text}")
        if "stopped" in msg_text.lower():
            logger.info(f"Slave {address} confirmed stopped.")
    if msg_type == 3:
        logger.info(
            f"RTT: Slave {address} pinged back in {time.perf_counter() - start_time:.9f} seconds."
        )


# 发送“开始”消息给slaves
def send_start_message(multicast_group, port, session_name, args):
    global sock
    if not is_listening:  # 如果没有监听，提示用户
        sg.popup_error("Please click 'Listen' before starting the session.")
        return

    session_name_len = len(session_name)
    if session_name_len > 128:
        logger.error("Session name too long!")
        return

    # 数据包格式: 状态码 (int4), 会话名字长度 (int4), 会话名字 (str)
    status = 1
    packed_data = struct.pack(
        f"!iii{session_name_len}s",
        status,
        args.record_time,
        session_name_len,
        session_name.encode("utf-8"),
    )

    # 打印发送的数据包
    logger.debug(f"Sending packed data: {packed_data}, length: {len(packed_data)}")

    # 使用已经创建的socket发送消息
    sock.sendto(packed_data, (multicast_group, port))
    on_start(session_name)


# 发送“停止”消息给slaves
def send_stop_message(multicast_group, port):
    global sock
    status = 2
    packed_data = struct.pack("!ii", status, 0)

    # 打印发送的数据包
    logger.debug(f"Sending packed data: {packed_data}, length: {len(packed_data)}")

    # 使用已经创建的socket发送消息
    sock.sendto(packed_data, (multicast_group, port))
    on_stop()


def send_ping_message(multicast_group, port):
    global sock
    global start_time
    start_time = time.perf_counter()
    status = 3
    packed_data = struct.pack("!ii", status, 114514)

    # 打印发送的数据包
    logger.debug(f"Sending packed data: {packed_data}, length: {len(packed_data)}")

    # 使用已经创建的socket发送消息
    sock.sendto(packed_data, (multicast_group, port))


# 接收slave回复的线程
def receive_slave_replies(reply_port, on_reply_callback):
    global sock
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.bind(("::", reply_port))  # 监听指定端口用于接收slave回复

    logger.info(f"Listening for replies on port {reply_port}")

    while is_listening:  # 当监听状态为True时
        try:
            data, address = sock.recvfrom(1024)  # 接收来自slave的回复
            if len(data) >= 12:  # 期望收到 状态码 (4字节), 类型字段 (4字节), 消息长度 (4字节)
                status, msg_type, msg_length = struct.unpack("!iii", data[:12])  # 解包状态码、消息类型和消息长度
                msg_text = data[12:12 + msg_length].decode("utf-8") if msg_length > 0 else ""
                on_reply_callback(address, status, msg_type, msg_length, msg_text)
        except Exception as e:
            logger.error(f"Error while receiving data: {e}")
            break

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

# 终止所有设备进程
def terminate_processes():
    for process in recording_processes:
        if process.poll() is None:
            process.terminate()
            logger.info(f"Terminated process with PID {process.pid}")

# 启动或重启监听
def restart_listen(multicast_address, reply_port):
    global is_listening, listen_thread, sock

    if is_listening:
        # 停止当前监听
        logger.info("Restarting listening")
        is_listening = False
        if sock:
            sock.close()  # 关闭套接字
        listen_thread.join()  # 等待旧的监听线程结束
        sock = None  # 重置socket

    # 启动新的监听
    logger.info("Starting listening")
    is_listening = True
    listen_thread = threading.Thread(
        target=receive_slave_replies, args=(reply_port, on_slave_reply), daemon=True
    )
    listen_thread.start()
    logger.info(f"Listening on {multicast_address}:{reply_port}")

# GUI部分
def main():
    global is_listening
    global start_time

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
        [sg.Text("Number of Clients"), sg.Input(default_text="2", key="client_num")],
        [
            sg.Text("Recording Time (seconds)"),
            sg.Input(default_text="20", key="record_time"),
        ],
        [sg.Text("Number of Devices"), sg.Input(default_text="2", key="device_num")],
        [
            sg.Text("Sync Delay (microseconds)"),
            sg.Input(default_text="160", key="sync_delay"),
        ],
        [
            sg.Button("Listen"),
            sg.Button("Start"),
            sg.Button("Stop"),
            sg.Button("Ping"),
        ],
        [
            sg.Text("<!> Notice: Click 'Listen' before starting the session."),
        ],
        [
            sg.Text(
                "<!> Notice: Master node cannot do a recording. Run a slave node instead."
            ),
        ],
    ]

    window = sg.Window(
        "KinectSync: Master Controller ver.1.2 by Kenvix <i@kenvix.com>", layout
    )

    # 主循环
    while True:
        event, values = window.read()

        if event == sg.WINDOW_CLOSED or event == "Exit":
            break

        session_name = values["session_name"]
        multicast_address = values["multicast_address"]
        port = int(values["port"])
        reply_port = int(values["reply_port"])
        
        if len(session_name) == 0:
            sg.popup_error("Please enter a session name.")
            continue
        elif len(session_name) > 192:
            sg.popup_error("Session name too long! (max 192 characters)")
            continue

        # 解析设备和录制参数
        args = argparse.Namespace(
            client_num=int(values["client_num"]),
            record_time=int(values["record_time"]),
            device_num=int(values["device_num"]),
            sync_delay=int(values["sync_delay"]),
            recorder_path="C:\\Program Files\\Azure Kinect SDK v1.4.2\\tools",
            save_path="./Goatdata",
        )

        if event == "Listen":
            # 重启监听
            restart_listen(multicast_address, reply_port)

        elif event == "Start":
            if not is_listening:  # 检查是否已经监听
                sg.popup_error("Please click 'Listen' before starting the session.")
            else:
                send_start_message(multicast_address, port, session_name, args)

        elif event == "Stop":
            if not is_listening:  # 检查是否已经监听
                sg.popup_error("Please click 'Listen' before starting the session.")
            else:
                send_stop_message(multicast_address, port)
                terminate_processes()
        elif event == "Ping":
            if not is_listening:  # 检查是否已经监听
                sg.popup_error("Please click 'Listen' before starting the session.")
            else:
                send_ping_message(multicast_address, port)

    window.close()


if __name__ == "__main__":
    main()
