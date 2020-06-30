#!/usr/bin/env python3
"""Command line entry point"""

import sys
import logging
import argparse
from pathlib import Path

import serial
from serial.tools import list_ports, list_ports_common

from . import core, name

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger()

def get_serial_device() -> list_ports_common.ListPortInfo:
    if sys.platform == "darwin":
        return next(list_ports.grep("usbserial"))
    return next(list_ports.grep("ttyusb0"))

def send(args: argparse.Namespace) -> None:
    """Send data file"""
    with open(str(args.file), "rb") as data_io:
        data = data_io.read()

    wire_data = core.WireFormat(args.file.name, data)
    try:
        usb_serial_port = args.device or get_serial_device()
    except StopIteration:
        LOG.critical("Serial device not found; exiting")
        sys.exit(3)
    with serial.Serial(usb_serial_port.device, baudrate=args.baudrate) as serial_device:
        core.send(wire_data, serial_device)

def listen(args: argparse.Namespace) -> None:
    """Listen for data"""
    try:
        usb_serial_port = args.device or get_serial_device()
    except StopIteration:
        LOG.critical("Serial device not found; exiting")
        sys.exit(1)
    with serial.Serial(usb_serial_port.device, baudrate=args.baudrate) as serial_device:
        while True:
            try:
                core.listen_and_write(serial_device)
            except core.ListenError:
                LOG.warning("Error; continuing")
                continue
            except KeyboardInterrupt:
                break

def main() -> None:
    """Entry point"""
    parser = argparse.ArgumentParser(prog=name,
                                     description="send and receive data")
    parser.add_argument("--baudrate", "-b", type=int, default=115200)
    parser.add_argument("--device", "-d", type=list_ports_common.ListPortInfo,
                        default=None)
    subparsers = parser.add_subparsers(title="subcommands",
                                       description="valid subcommands")
    listen_parser = subparsers.add_parser("listen", aliases=["l"])
    send_parser = subparsers.add_parser("send", aliases=["s"])
    send_parser.add_argument("file", type=Path, metavar="FILE")
    listen_parser.set_defaults(func=listen)
    send_parser.set_defaults(func=send)
    args = parser.parse_args()

    try:
        args.func(args)
    except AttributeError:
        parser.print_help(sys.stderr)
        sys.exit(4)

if __name__ == "__main__":
    main()
