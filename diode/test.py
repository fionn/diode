#!/usr/bin/env python3
"""Unit tests for sending and receiving across the serial connection"""

import sys
import queue
import unittest
import threading
import subprocess
from binascii import crc32
from typing import NamedTuple, Any, Optional, Union

import serial

from diode.core import send, listen, WireFormat, ListenError, LOG

LOG.disabled = True

SerialProcess = NamedTuple("SerialProcess", [("process", subprocess.Popen[str]),
                                             ("devices", list[str])])

class ExcThread(threading.Thread):
    """Thread child to catch exceptions and raise on join"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.exception: BaseException = None

    def run(self) -> None:
        try:
            self._target(*self._args, **self._kwargs) # type:ignore
        except BaseException as exception: # pylint: disable=broad-except
            self.exception = exception

    def join(self, timeout: Optional[Union[int, float]] = None) -> None:
        super().join(timeout=timeout)
        if self.exception:
            raise self.exception

class BaseTestSerialDevice(unittest.TestCase):
    """Base class to initialise serial device"""

    socat: SerialProcess = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.socat = cls._create_serial_devices()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.socat.process.kill()

    @staticmethod
    def _create_serial_devices() -> SerialProcess:
        """Oh jeez this is pretty horrible"""
        cmd = ["socat", "-d", "-d", "pty,raw,echo=0", "pty,raw,echo=0"]
        process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True) # pylint: disable=consider-using-with
        ttys = []
        for line in iter(process.stderr.readline, ""):
            sys.stderr.flush()
            if " N PTY is " in line:
                ttys.append(line.strip().split(" N PTY is ")[1])
            if "starting data transfer loop with FDs" in line:
                break
        return SerialProcess(process, ttys)

class TestSend(BaseTestSerialDevice):
    """Tests for sending WireFormat data"""

    def test_send(self) -> None:
        """Send WireFormat data"""
        wire_data = WireFormat("metadata", b"payload")
        with serial.Serial(self.socat.devices[0]) as serial_device:
            send(wire_data, serial_device)

    def test_send_too_much_metadata(self) -> None:
        """Send with overflowing metadata"""
        wire_data = WireFormat(33 * "A", b"payload")
        with serial.Serial(self.socat.devices[0]) as serial_device:
            with self.assertRaises(OverflowError):
                send(wire_data, serial_device)

class TestListen(BaseTestSerialDevice):
    """Tests for receiving data over the serial connection"""

    @staticmethod
    def _queued_listener(que: queue.Queue[WireFormat], device: str) -> None:
        que.put(listen(device))

    def test_listen(self) -> None:
        """Receive WireFormat data"""
        wire_data = WireFormat("metadata", b"payload")
        with serial.Serial(self.socat.devices[1]) as listen_device:
            que: queue.Queue[WireFormat] = queue.Queue()
            listen_thread = threading.Thread(target=self._queued_listener,
                                             args=(que, listen_device))
            listen_thread.start()
            with serial.Serial(self.socat.devices[0]) as serial_device:
                send(wire_data, serial_device)
            listen_thread.join()
            self.assertEqual(wire_data, que.get())

    def test_listen_no_sot(self) -> None:
        """Receive WireFormat data"""
        with serial.Serial(self.socat.devices[1]) as listen_device:
            listen_thread = ExcThread(target=listen,
                                      args=(listen_device,))
            listen_thread.start()
            with serial.Serial(self.socat.devices[0]) as serial_device:
                serial_device.write(b"x")
                with self.assertRaises(ListenError):
                    listen_thread.join()

    def test_listen_short_metadata(self) -> None:
        """Receive WireFormat data with not enough metadata"""
        with serial.Serial(self.socat.devices[1], timeout=0.2) as listen_device:
            listen_thread = ExcThread(target=listen,
                                      args=(listen_device,))
            listen_thread.start()
            metadata = "metadata"
            with serial.Serial(self.socat.devices[0]) as ser:
                ser.write(b"\x02") # SOT
                ser.write(metadata.ljust(31, "\0").encode())
            with self.assertRaises(ListenError):
                listen_thread.join()

    def test_listen_zero_length_data(self) -> None:
        """Receive WireFormat data zero length"""
        with serial.Serial(self.socat.devices[1]) as listen_device:
            listen_thread = ExcThread(target=listen,
                                      args=(listen_device,))
            listen_thread.start()
            metadata = "metadata"
            data = b"data"
            with serial.Serial(self.socat.devices[0]) as ser:
                ser.write(b"\x02") # SOT
                ser.write(metadata.ljust(32, "\0").encode())
                ser.write(int(0).to_bytes(8, byteorder="big"))
                ser.write(data)

            with self.assertRaises(ListenError):
                listen_thread.join()

    def test_listen_data_overflow(self) -> None:
        """Receive WireFormat too much data"""
        with serial.Serial(self.socat.devices[1]) as listen_device:
            listen_thread = ExcThread(target=listen,
                                      args=(listen_device,))
            listen_thread.start()
            metadata = "metadata"
            data = b"data"
            with serial.Serial(self.socat.devices[0]) as ser:
                ser.write(b"\x02") # SOT
                ser.write(metadata.ljust(32, "\0").encode())
                ser.write(len(data).to_bytes(8, byteorder="big"))
                ser.write(data + b"yolo")

            with self.assertRaises(ListenError):
                listen_thread.join()

    def test_listen_bad_etx(self) -> None:
        """Receive WireFormat data bad ETX"""
        with serial.Serial(self.socat.devices[1]) as listen_device:
            listen_thread = ExcThread(target=listen,
                                      args=(listen_device,))
            listen_thread.start()
            metadata = "metadata"
            data = b"data"
            with serial.Serial(self.socat.devices[0]) as ser:
                ser.write(b"\x02") # SOT
                ser.write(metadata.ljust(32, "\0").encode())
                ser.write(len(data).to_bytes(8, byteorder="big"))
                ser.write(data)
                ser.write(b"\x04") # EOT, not ETX

            with self.assertRaises(ListenError):
                listen_thread.join()

    def test_listen_bad_crc32(self) -> None:
        """Receive WireFormat data with bad CRC32"""
        with serial.Serial(self.socat.devices[1]) as listen_device:
            listen_thread = ExcThread(target=listen,
                                      args=(listen_device,))
            listen_thread.start()
            metadata = "metadata"
            data = b"data"
            with serial.Serial(self.socat.devices[0]) as ser:
                ser.write(b"\x02") # SOT
                ser.write(metadata.ljust(32, "\0").encode())
                ser.write(len(data).to_bytes(8, byteorder="big"))
                ser.write(data)
                ser.write(b"\x03") # ETX
                ser.write((crc32(b"bata") & 0xffffffff).to_bytes(8, byteorder="big"))

            with self.assertRaises(ListenError):
                listen_thread.join()

def main() -> None:
    """Entry point for test runner"""
    unittest.main(verbosity=2)

if __name__ == "__main__":
    main()
