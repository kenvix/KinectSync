import socket
import datetime
import os
import subprocess
import re
import argparse
from loguru import logger
from typing import List
from libs import processutils


def setup_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=str, default="192.168.137.1", help="ip address")
    parser.add_argument(
        "--port", type=int, default=8890, help="port number", required=False
    )
    parser.add_argument("-t", "--record_time", type=int, default=20, help="record time")
    parser.add_argument(
        "--recorder_path",
        type=str,
        default="C:\\Program Files\\Azure Kinect SDK v1.4.2\\tools",
        help="recorder path",
    )
    parser.add_argument(
        "--save_path", type=str, default="C:\\0_goatdata", help="save root path"
    )
    return parser.parse_args()


def create_save_folder(base_path: str) -> str:
    now: str = datetime.datetime.now().strftime("%Y-%m-%d")
    save_path: str = (
        os.path.join(base_path, now)
        if base_path[-1] not in ["\\", "/"]
        else base_path + now
    )
    os.makedirs(save_path, exist_ok=True)
    logger.info(f"Save path created or already exists: {save_path}")
    return save_path


def run_recorder(
    device_id: int,
    sync_type: str,
    delay: int,
    record_time: int,
    save_file_name: str,
    recorder_path: str,
    process_list: List[subprocess.Popen],
) -> None:
    """Helper function to run the k4arecorder with specified parameters."""
    command: str = (
        f"k4arecorder.exe --device {device_id} --external-sync {sync_type} "
        f'--sync-delay {delay} -d WFOV_2X2BINNED -c 1080p -r 30 -l {record_time} "{save_file_name}"'
    )
    process: subprocess.Popen = subprocess.Popen(
        command,
        shell=True,
        cwd=recorder_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    logger.debug(f"$ {command}")
    processutils.set_high_priority(process.pid)
    process_list.append(process)
    logger.info(f"Started recording on device {device_id}, saving to {save_file_name}")


def record_video(
    id: str,
    save_path: str,
    record_time: int,
    recorder_path: str,
    process_list: List[subprocess.Popen],
) -> str:
    """Handles video recording setup for multiple devices."""
    current_round: int = len(os.listdir(save_path)) // 2 + 1
    save_file_name0: str = os.path.join(save_path, f"sheep_{current_round}_{id}_2.mkv")
    save_file_name1: str = os.path.join(save_path, f"sheep_{current_round}_{id}_3.mkv")

    # Call the helper function for both devices and track the processes
    run_recorder(
        1, "Subordinate", 320, record_time, save_file_name1, recorder_path, process_list
    )
    run_recorder(
        0, "Subordinate", 320, record_time, save_file_name0, recorder_path, process_list
    )

    for p in process_list:
        processutils.read_until_signal(p)

    logger.info(f"Started recording for sheep ID {id} - round {current_round}")
    return "ready"


def terminate_processes(process_list: List[subprocess.Popen]) -> None:
    """Terminate all running processes in the list."""
    for process in process_list:
        if process.poll() is None:  # Check if the process is still running
            process.terminate()  # Terminate the process
            logger.info(f"Terminated process with PID {process.pid}")


def main() -> None:
    args: argparse.Namespace = setup_arguments()
    
    processutils.check_system_and_set_priority()

    # Create the save folder
    save_path: str = create_save_folder(args.save_path)

    # Create and connect the socket
    sk: socket.socket = socket.socket()
    sk.connect((args.ip, args.port))
    logger.info("Connected to the server")

    # List to track running processes
    process_list: List[subprocess.Popen] = []

    try:
        while True:
            ret: bytes = sk.recv(1024)

            if b"start" in ret:
                id: str = re.findall(r"\d+\.?\d*", ret.decode("utf-8"))[0]
                logger.info(f"Preparing to record video for sheep ID: {id}")

                ret_message: str = record_video(
                    id, save_path, args.record_time, args.recorder_path, process_list
                )
                sk.send(ret_message.encode("utf-8"))

            if ret == b"bye":
                terminate_processes(process_list)
                sk.send(b"bye")
                logger.info("Session ended by server")
                break
    except Exception as e:
        logger.error(f"Client error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure all processes are terminated when the session ends
        terminate_processes(process_list)

        # Close the socket
        sk.close()
        logger.info("Socket closed")


if __name__ == "__main__":
    main()
