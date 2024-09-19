from loguru import logger

logger.info("PWM Controller ver.1.0 by Kenvix <i@kenvix.com>")

import FreeSimpleGUI as sg
import serial
import traceback
import threading
import time
from libs import processutils

sg.theme("DarkAmber")

layout = [
    [sg.Text("PWM Frequency  in Hz\t"), sg.InputText("030")],
    [sg.Text("PWM Duty Cycle in  %\t"), sg.InputText("050")],
    [sg.Text("PWM Slot (1/2/3)\t\t"), sg.InputText("1")],
    [sg.Text("Serial Baud\t\t"), sg.InputText("9600")],
    [sg.Text("Serial Port\t\t"), sg.InputText("COM5")],
    [sg.Button("Connect Serial"), sg.Button("✔️ Start"), sg.Button("❌ Stop")],
]

com: serial.Serial = None
com_thread = None

stop_event = threading.Event()
def com_reader():
    while not stop_event.is_set():
        print(com.read().decode('ascii'), end='')

# 创造窗口
window = sg.Window("PWM Controller ver.1.0 by Kenvix <i@kenvix.com>", layout)

if not processutils.check_system_and_set_priority():
    sg.popup_error("Not running with admin/root privileges. Cannot set process priority. Please, run this program with admin/root.")

# 事件循环并获取输入值
while True:
    try:
        event, values = window.read()
        if event is None:
            # stop_event.set()
            exit(0)
        elif 'Start' in event:  # 如果用户关闭窗口或点击`Cancel`
            if com is None:
                continue
            pwmFreq = values[0]
            pwmDuty = values[1]
            pwmSlot = values[2]
            com.write(f"dU{pwmSlot}:{pwmDuty}".encode("ascii"))
            status_duty = com.read_until(b"\n")
            com.write(f"FR{pwmSlot}:{pwmFreq}".encode("ascii"))
            status_freq = com.read_until(b"\n")
            logger.info(
                f"Started PWM in {pwmFreq}Hz {pwmDuty}% [Duty {status_duty} Freq {status_freq}]"
            )
            continue
        elif "Stop" in event:
            if com is None:
                continue
            pwmSlot = values[2]
            com.write(f"FR{pwmSlot}:000".encode("ascii"))
            status_freq = com.read_until(b"\n")
            logger.info(f"Stopped PWM {status_freq}")
            continue
        elif "Connect Serial" in event:
            logger.info(f"Connect Serial")
            if com is not None:
                # stop_event.set()
                com.close()
            com = serial.Serial()
            com.port = values[4]  # 串口设备路径
            com.baudrate = int(values[3])  # 波特率
            com.bytesize = serial.EIGHTBITS  # 数据位长度为8位
            com.parity = serial.PARITY_NONE  # 无奇偶校验
            com.stopbits = serial.STOPBITS_ONE  # 1位停止位
            com.timeout = 1  # 读取超时时间为1秒
            com.open()
            logger.info(f"Connected Serial")
            # com_thread = threading.Thread(target=com_reader)
            # com_thread.start()
            continue
        logger.trace("You entered ", values)
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        sg.popup_error(e)

window.close()
