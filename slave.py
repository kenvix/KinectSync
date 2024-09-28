import socket
import struct
import subprocess
from typing import List
from loguru import logger
import argparse
import os
import datetime
from libs import processutils
import socket

# 获取主机名称
pc_name = socket.gethostname()

# 发送状态消息给 master，自动使用 master 的来源地址，并添加消息长度和文本字段
def send_status_to_master(master_addr, port, status_code, msg_type, msg_text=""):
    with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as sock:
        strbytes = msg_text.encode("utf-8")
        msg_length = len(strbytes)
        packed_status = struct.pack(
            "!iii", status_code, msg_type, msg_length
        )  # 状态码, 类型, 消息长度
        packed_message = packed_status + strbytes
        sock.sendto(packed_message, (master_addr, port))
    logger.info(
        f"Sent status to {master_addr}, status_code: {status_code}, msg_type: {msg_type}, msg_text: {msg_text}"
    )


# 启动录像进程
def start_recording(
    args: argparse.Namespace,
    save_path: str,
    process_list: List[subprocess.Popen],
    master_addr,
    reply_port,
    session_name,
    record_time,
):
    try:
        current_round = len(os.listdir(save_path)) // 2 + 1

        for i in range(args.device_num):
            sync_delay = (args.device_offset + i) * args.sync_delay
            save_file_name = f"{save_path}/{session_name}-{pc_name}-Device{i}.mkv"
            record_command = (
                f"k4arecorder.exe --device {i} --external-sync Subordinate "
                f'--sync-delay {sync_delay} -d WFOV_2X2BINNED -c 1080p -r 30 -l {record_time} "{save_file_name}"'
            )

            process = subprocess.Popen(
                record_command,
                shell=True,
                cwd=args.recorder_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            logger.debug(
                f"Started {record_time}s recording [{session_name}] on device {i}, command: {record_command}"
            )
            process_list.append(process)

        # 监控所有进程
        for p in process_list:
            processutils.read_until_signal(p)

        # 成功时回报给 master
        send_status_to_master(master_addr, reply_port, 0, 1)
    except Exception as e:
        error_message = f"Recording failed: {e}"
        logger.error(error_message)
        send_status_to_master(master_addr, reply_port, -1, 1, error_message)


# 停止所有录像进程
def stop_recording(process_list: List[subprocess.Popen], master_addr, reply_port):
    try:
        for process in process_list:
            if process.poll() is None:
                process.terminate()
                logger.info(f"Terminated process with PID {process.pid}")

        send_status_to_master(master_addr, reply_port, 0, 2)  # 成功停止录像
    except Exception as e:
        error_message = f"Failed to stop recording: {e}"
        logger.error(error_message)
        send_status_to_master(master_addr, reply_port, -1, 2, error_message)


# 监听组播
def listen_multicast(multicast_group, port, reply_port, args, process_list):
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # 绑定到所有接口的指定端口
    sock.bind(("::", port))

    # 加入组播组
    group_bin = socket.inet_pton(socket.AF_INET6, multicast_group)
    mreq = group_bin + struct.pack("I", 0)  # 0代表所有接口
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)

    logger.info(f"Listening for multicast messages on {multicast_group}:{port}")

    while True:
        data, address = sock.recvfrom(1024)
        master_addr = address[0]
        logger.info(f"Received message from {master_addr}")

        if len(data) >= 8:  # 期望收到 状态码 和 会话名字长度
            status, record_time, session_name_len = struct.unpack("!iii", data[:12])

            if status == 1:  # Start command
                session_name = data[12 : 12 + session_name_len].decode("utf-8")
                logger.info(
                    f"Starting {record_time}s recording [{session_name}] for session: {session_name}"
                )
                start_recording(
                    args,
                    args.save_path,
                    process_list,
                    master_addr,
                    reply_port,
                    session_name,
                    record_time,
                )

            elif status == 2:  # Stop command
                logger.info("Stopping recording")
                stop_recording(process_list, master_addr, reply_port)

            elif status == 3:  # Stop command
                logger.info("Master ping")
                send_status_to_master(master_addr, reply_port, 0, 3)


if __name__ == "__main__":
    # 通过 argparse 处理命令行参数
    parser = argparse.ArgumentParser(
        description="Slave node for multicast communication."
    )
    parser.add_argument(
        "--multicast_group",
        type=str,
        default="ff02:ca11:4514:1919::",
        help="Multicast group address",
    )
    parser.add_argument("--port", type=int, default=4329, help="Port to listen on")
    parser.add_argument(
        "--reply_port", type=int, default=4328, help="Port to send replies to"
    )
    parser.add_argument("--device_num", type=int, default=2, help="Number of devices")
    parser.add_argument(
        "-o", "--device_offset", type=int, default=0, help="device sync delay offset"
    )
    parser.add_argument(
        "--sync_delay", type=int, default=160, help="Sync delay in microseconds"
    )
    parser.add_argument(
        "--recorder_path",
        type=str,
        default="C:\\Program Files\\Azure Kinect SDK v1.4.2\\tools",
        help="Path to k4arecorder",
    )
    parser.add_argument(
        "--save_path",
        type=str,
        default="./Goatdata",
        help="Root path to save recordings",
    )

    args = parser.parse_args()

    # List to track running processes
    process_list: List[subprocess.Popen] = []

    # 启动监听
    listen_multicast(
        args.multicast_group, args.port, args.reply_port, args, process_list
    )
