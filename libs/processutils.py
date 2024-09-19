import os
import platform
import psutil
import ctypes
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

def set_high_priority():
    """Set the process priority to the highest level based on the operating system."""
    if platform.system().lower() == 'windows':
        import win32api, win32process, win32con
        # Set REALTIME_PRIORITY_CLASS for Windows
        REALTIME_PRIORITY_CLASS = 0x00000100
        try:
            pid = win32api.GetCurrentProcessId()
            handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
            win32process.SetPriorityClass(handle, win32process.REALTIME_PRIORITY_CLASS)
            logger.info("Windows: Process priority has been set to the highest (REALTIME_PRIORITY_CLASS).")
        except Exception as e:
            logger.error(f"Error occurred while setting priority: {e}")
    elif platform.system().lower() == 'linux':
        # Set the highest priority (-20) for Linux
        try:
            import os
            os.nice(-20)
            logger.info("Linux: Process priority has been set to the highest (-20).")
        except psutil.AccessDenied:
            logger.error("Failed to set priority: No root privileges.")
        except Exception as e:
            logger.error(f"Error occurred while setting priority: {e}")
    else:
        logger.warning("Unsupported operating system.")

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
