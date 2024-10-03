import os
import platform
import subprocess

import ctypes
import sys
from loguru import logger

def check_admin():
    """Check if the script is running with admin/root privileges."""
    if platform.system().lower() == 'windows':
        # Check for admin rights on Windows
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    elif platform.system().lower() == 'linux':
        # Check for root privileges on Linux
        return os.geteuid() == 0
    else:
        return False


def make_dpi_aware():
    if sys.platform == "win32":  # 仅在 Windows 上执行
        try:
            # 设置每个监视器 DPI 感知（Windows 8.1 及以上）
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                # 如果 Windows 8.1 的 DPI 感知失败，使用 Windows 10 的函数
                ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
            except Exception:
                # 如果两者都不可用，使用 Windows 7 的DPI设置
                ctypes.windll.user32.SetProcessDPIAware()


def set_high_priority(target_pid=None):
    """Set the process priority to the highest level based on the operating system."""
    if platform.system().lower() == 'windows':
        import win32api, win32process, win32con
        # Set REALTIME_PRIORITY_CLASS for Windows
        REALTIME_PRIORITY_CLASS = 0x00000100
        try:
            pid = win32api.GetCurrentProcessId() if target_pid is None else target_pid
            handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
            win32process.SetPriorityClass(handle, win32process.REALTIME_PRIORITY_CLASS)
            error = win32api.GetLastError()
            logger.info(
                f"Windows: Process {pid} priority has been set to the highest ({error})."
            )
            win32api.CloseHandle(handle)

        except Exception as e:
            logger.error(f"Error occurred while setting priority: {e}")
    else:
        # Set the highest priority (-20) for Linux
        try:
            import psutil
            psutil.Process(target_pid).nice(-20)
            logger.info("Linux: Process priority has been set to the highest (-20).")
        except psutil.AccessDenied:
            logger.error("Failed to set priority: No root privileges.")
        except Exception as e:
            logger.error(f"Error occurred while setting priority: {e}")

def check_system_and_set_priority():
    """Check the operating system and set the process priority to the highest level if admin/root."""
    if check_admin():
        logger.info("Running with admin/root privileges.")
        set_high_priority()
        return True
    else:
        logger.warning("Not running with admin/root privileges. Cannot set process priority.")
        logger.warning("Please, run this program with admin/root.")
        return False


def read_until_signal(process: subprocess.Popen):
    # 持续读取输出，直到检测到目标字符串
    try:
        while True:
            if process.poll() is None:
                output = process.stdout.read()
                logger.debug(f"Pid {process.pid}: {output.strip()}")
                logger.error(f"Pid {process.pid} is dead with code {process.wait()}")
                return False
            output = process.stdout.readline()
            logger.debug(f"Pid {process.pid}: {output.strip()}")
            if output == "" and process.poll() is not None:
                break
            if "Waiting for signal from master" in output:
                logger.info(f"Pid {process.pid} - Signal detected!")
                break
    except Exception as e:
        ...
