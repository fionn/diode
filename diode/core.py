"""Core functionality for serial diode"""

import time
import logging
from pathlib import Path
from binascii import crc32
from typing import NamedTuple
from tempfile import gettempdir

import serial

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger()

WireFormat = NamedTuple("WireFormat", [("metadata", str), ("data", bytes)])

class ListenError(Exception):
    """Wire format protocol violation"""

def write_bytes(ser: serial.Serial, packet: bytearray, pause: float = None) -> int:
    """Throttled write to serial device"""
    # https://en.wikipedia.org/wiki/Universal_asynchronous_receiver-transmitter#Data_framing
    pause = pause or 10 / ser.baudrate
    count = 0
    for byte in packet:
        count += ser.write(bytes([byte]))
        time.sleep(pause)
    return count

def send(wire_data: WireFormat, ser: serial.Serial) -> None:
    """
    Format is
    ┌─────┬──────────┬─────────────┬──────┬─────┬───────┐
    │ SOT │ metadata │ data_length │ data │ EXT │ crc32 │
    └─────┴──────────┴─────────────┴──────┴─────┴───────┘
    for metadata: 32 bytes
        data_length: 8 bytes
        data: data_length bytes
        crc32: 8 bytes
    and SOT, EXT 1 byte each.
    """

    if len(wire_data.metadata) >= 32:
        raise OverflowError("File name must be less than 32 bytes")

    packet = bytearray()

    packet.extend(b"\x02") # SOT
    packet.extend(wire_data.metadata.ljust(32, "\0").encode())
    packet.extend(len(wire_data.data).to_bytes(8, byteorder="big"))
    packet.extend(wire_data.data)
    packet.extend(b"\x03") # ETX
    packet.extend((crc32(wire_data.metadata.ljust(32, "\0").encode()
                         + wire_data.data) & 0xffffffff).to_bytes(8, byteorder="big"))

    write_bytes(ser, packet)
    ser.flush()
    ser.reset_input_buffer()
    ser.reset_output_buffer()

def listen(ser: serial.Serial) -> WireFormat:
    """
    Listen on a serial port and return WireFormat data if matching protocol
    data is received
    """
    serial_byte = ser.read()
    if serial_byte == b"\x02": # SOT
        filename = ser.read(32).decode().rstrip("\0")
        length = int.from_bytes(ser.read(8), byteorder="big")
        data = ser.read(length)
        etx = ser.read()
        if etx != b"\x03":
            LOG.info("Missed ETX")
            raise ListenError
        checksum = int.from_bytes(ser.read(8), byteorder="big")
        checksum &= 0xffffffff
        if (crc32(filename.ljust(32, "\0").encode() + data) & 0xffffffff) != checksum:
            LOG.info("Received checksum %s but calculated checksum %s",
                     checksum, crc32(data + filename.ljust(32, "\0").encode()) & 0xffffffff)

            raise ListenError("Received checksum {} but calculated checksum {}".format( \
                     checksum, crc32(data + filename.ljust(32, "\0").encode()) & 0xffffffff))
        LOG.info("Received data")
        return WireFormat(filename, data)

    raise ListenError

def write_to_dir(wire_data: WireFormat, out_dir: Path) -> None:
    out_dir.mkdir(exist_ok=True)
    output = out_dir / Path(wire_data.metadata).name
    output.touch(mode=0o600, exist_ok=True)
    count = output.write_bytes(wire_data.data)
    LOG.info("%d bytes written to %s", count, output)

def listen_and_write(serial_device: serial.serialposix.Serial,
                     out_dir: Path = None) -> None:
    """Dump data to given directory"""
    wire_data = listen(serial_device)
    out_dir = out_dir or Path(gettempdir())
    write_to_dir(wire_data, out_dir)
