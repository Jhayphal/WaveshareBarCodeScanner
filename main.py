import warnings

import serial
import crc16
import time


warnings.filterwarnings("ignore", category=DeprecationWarning)


def int_to_crc16(crc: int) -> list:
    return [(crc & 0xFF00) >> 8, crc & 0x00FF]


def create_read_request(address: list, data_length: int) -> list:
    header1 = [0x7E, 0x00]
    types = 0x07
    lens = 0x01

    crc_data = [types, lens]
    crc_data.extend(address)
    crc_data.append(data_length)
    crc = crc16.crc16xmodem(bytes(crc_data))

    request = []
    request.extend(header1)
    request.append(types)
    request.append(lens)
    request.extend(address)
    request.append(data_length)
    request.extend(int_to_crc16(crc))

    return request


def read_response(uart_port: serial.Serial) -> list:
    result_frame = True
    result_data = []

    while result_frame:
        result_frame = uart_port.read()

        if result_frame:
            result_data.append(int(result_frame[0]))

        time.sleep(0.001)

    return result_data


def is_valid_read_response(result_data: list, data_length: int) -> bool:
    if len(result_data) == 0 or len(result_data) < 6 + data_length:
        return False

    if not (0x02 == result_data[0]):
        return False

    if not (0x00 == result_data[1]):
        return False

    if not (0x00 == result_data[2]):
        return False

    if not (data_length == result_data[3]):
        return False

    crc_data = result_data[2:-2]

    crc = crc16.crc16xmodem(bytes(crc_data))
    crc16_data = int_to_crc16(crc)

    if crc16_data != result_data[-2:]:
        return False

    return True


def is_valid_write_response(result_data: list) -> bool:
    if len(result_data) == 0 or len(result_data) != 7:
        return False

    return [0x02, 0x00, 0x00, 0x01, 0x00, 0x33, 0x31] == result_data


def read_address(uart_port: serial.Serial, address: list, data_length: int) -> list:
    request = create_read_request(address, data_length)
    uart_port.write(bytes(request))

    time.sleep(0.25)

    result_data = read_response(uart_port)

    if not is_valid_read_response(result_data, data_length):
        return []

    return result_data[4:-2]


def create_write_request(address: list, data: list) -> list:
    header1 = [0x7E, 0x00]
    types = 0x08
    lens = len(data)

    if lens > 256:
        raise OverflowError()

    elif lens == 256:
        lens = 0

    crc_data = [types, lens]
    crc_data.extend(address)
    crc_data.extend(data)
    crc = crc16.crc16xmodem(bytes(crc_data))

    request = []
    request.extend(header1)
    request.append(types)
    request.append(lens)
    request.extend(address)
    request.extend(data)
    request.extend(int_to_crc16(crc))

    return request


def write_address(uart_port: serial.Serial, address: list, data: list) -> bool:
    request = create_write_request(address, data)
    uart_port.write(bytes(request))

    time.sleep(0.25)

    result_data = read_response(uart_port)

    if not is_valid_write_response(result_data):
        return False

    return True


def set_scanning_mode(scan: bool) -> bool:
    mode = 0x00

    if scan:
        mode = 0x01

    state = read_address(port, [0x00, 0x02], 0x01)

    if len(state) == 0:
        return True

    state = state[0]

    if state == mode:
        return True

    time.sleep(0.1)

    return write_address(port, [0x00, 0x02], [mode])


port = serial.Serial(
    port='COM3',  # /dev/ttyS0
    parity=serial.PARITY_NONE,
    bytesize=serial.EIGHTBITS,
    stopbits=serial.STOPBITS_ONE,
    timeout=0,
    xonxoff=0,
    rtscts=0,
    dsrdtr=0,
    baudrate=9600)

scanning_interval = read_address(port, [0x00, 0x06], 0x01)

if len(scanning_interval) > 0:
    scanning_interval = scanning_interval[0] / 10.0
else:
    scanning_interval = 0.0

if scanning_interval == 0.0:
    scanning_interval = 15

time.sleep(0.1)

if not set_scanning_mode(True):
    raise Exception("write error")

print(scanning_interval)

estimate = 0.0
step = 0.01
result = []
data_frame = False

while data_frame or estimate < scanning_interval:
    data_frame = port.read()

    if data_frame:
        result.append(data_frame)

    elif len(result) > 0:
        break

    time.sleep(step)

    estimate += step

print(''.join(chr(i[0]) for i in result))

if not set_scanning_mode(False):
    raise Exception("write error")

port.close()
