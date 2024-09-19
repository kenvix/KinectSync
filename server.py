import socket
import os
import datetime
import subprocess
import time
import argparse
import re
from typing import List
from loguru import logger

from libs import processutils

processutils.check_system_and_set_priority()

def create_directory(path: str) -> None:
    """Create a directory if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)


def initiate_connection(
    server_socket: socket.socket, client_count: int
) -> List[socket.socket]:
    """Accept client connections until the specified number of clients have connected."""
    connected_clients: List[socket.socket] = []
    while len(connected_clients) < client_count:
        conn, addr = server_socket.accept()
        logger.info(f"Client {addr} connected.")
        connected_clients.append(conn)
    return connected_clients


def broadcast_message(clients: List[socket.socket], message: str) -> None:
    """Send a message to all connected clients."""
    for conn in clients:
        conn.send(bytes(message, encoding="utf-8"))


def receive_readiness(clients: List[socket.socket]) -> int:
    """Receive readiness signals from all clients."""
    ready_count: int = 0
    for conn in clients:
        if conn.recv(1024) == b"ready":
            ready_count += 1
            logger.info(f"Client {conn.getpeername()} is ready.")
    return ready_count


def execute_recording(
    record_command: str, recorder_path: str, delay: int = 2
) -> subprocess.Popen:
    """Execute recording command and wait for a short delay."""
    process = subprocess.Popen(
        record_command,
        shell=True,
        cwd=recorder_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    logger.debug(f"$ {record_command}")
    processutils.set_high_priority(process.pid)
    return process


def terminate_processes(processes: List[subprocess.Popen]) -> None:
    """Terminate all running processes."""
    for process in processes:
        if process.poll() is None:  # If process is still running
            process.terminate()
            logger.info(f"Process {process.pid} terminated.")


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=str, default="0.0.0.0", help="IP address")
    parser.add_argument("--port", type=int, default=8890, help="Port number")
    parser.add_argument("--client_num", type=int, default=1, help="Client number")
    parser.add_argument("--record_time", type=int, default=20, help="Record time")
    parser.add_argument("-d", "--device_num", type=int, default=2, help="device num")
    parser.add_argument(
        "--recorder_path",
        type=str,
        default="C:\\Program Files\\Azure Kinect SDK v1.4.2\\tools",
        help="Recorder path",
    )
    parser.add_argument(
        "--save_path", type=str, default="./Goatdata", help="Save root path"
    )
    args: argparse.Namespace = parser.parse_args()
    logger.debug(args)

    # Directory setup
    create_directory(args.save_path)
    now: str = datetime.datetime.now().strftime("%Y-%m-%d")
    save_path: str = os.path.join(args.save_path, now)
    create_directory(save_path)

    # Server setup
    sk: socket.socket = socket.socket()
    sk.bind((args.ip, args.port))
    logger.info(f"Server started, waiting for {args.client_num} client connections...")
    sk.listen()

    client_num: int = args.client_num
    connected_clients: List[socket.socket] = initiate_connection(sk, client_num)

    recording_processes: List[subprocess.Popen] = []

    try:
        while True:
            info: str = input(">>> ")
            broadcast_message(connected_clients, info)
            id: List[str] = re.findall(r"\d+\.?\d*", info)
            ready_count: int = receive_readiness(connected_clients)

            if ready_count == client_num:
                logger.info(
                    f"All devices are ready. Currently recording round {len(os.listdir(save_path)) // 2 + 1}, Goat ID: {id[0]}"
                )

                for i in range(args.device_num):
                    record_command: str = (
                        f'k4arecorder.exe --device {i} --external-sync Subordinate --sync-delay 320 -d WFOV_2X2BINNED -c 1080p -r 30 -l {args.record_time} "{save_path}\\Goat_{len(os.listdir(save_path)) // 2 + 1}_{id[0]}_{i}.mkv"'
                    )

                    p = execute_recording(record_command, args.recorder_path)

                    # Append the processes to the list
                    recording_processes.append(p)

                for p in recording_processes:
                    processutils.read_until_signal(p)
            elif info == "bye":
                logger.info("Received 'bye' signal, terminating all processes.")
                terminate_processes(recording_processes)
            else:
                logger.warning("Some devices are not ready.")

    except socket.timeout:
        logger.error(
            "Timeout: No client connected within the allowed time. Server terminated."
        )
    except Exception as e:
        logger.error(f"Server error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Terminate all processes
        terminate_processes(recording_processes)
        for conn in connected_clients:
            conn.send(bytes("bye", encoding="utf-8"))
            conn.close()
        sk.close()


if __name__ == "__main__":
    main()
