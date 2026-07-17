import serial
import time

PORT = "COM6"
BAUD = 921600

try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)
    print("Connected to radar sensor...\n")

    while True:
        data = ser.read(1024)
        if data:
            print(data)

except Exception as e:
    print("Error:", e)