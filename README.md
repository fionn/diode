# Serial Diode

Generic wire protocol and implementation for one-way data transfer over UART serial.

## Usage

### General

The serial device can be specified with `--device` and baudrate with `--baudrate`.
If device is unspecified, it will attempt to guess the correct device based on platform and name.
If baudrate is unspecified, it defaults to 115200 Hz.

See `--help` for detailed usage information.

### Send

Run `diode send <path/to/file>` to send `<file>`.

### Receive

Run `diode listen`, which will listen forever. When it receives a valid payload, it will write it to `out/<file>` where `<file>` was specified in the payload metadata.

Note that on some systems this may need to be run as root to allow access to the serial port.
It is generally preferable to add the user to the appropriate group with something similar to `usermod -a -G uucp <username>`.

## Wire format

    ┌─────┬──────────┬─────────────┬──────┬─────┬───────┐
    │ SOT │ metadata │ data_length │ data │ EXT │ crc32 │
    └─────┴──────────┴─────────────┴──────┴─────┴───────┘

Here:
* `metadata` is 32 bytes,
* `data_length` is 8 bytes,
* `data` is `data_length` bytes,
* `crc32` is 8 bytes,
* `SOT` and `EXT` are the bytes `x02`, `x03`,
* `crc32` is the value of the CRC32 function acting on `metadata || data`.

## Installation

Install in developer mode with `make install_dev && source venv/bin/activate`.

Install as user with `make install`.

Install Bash completion with `source bash_completion/diode`.

## Testing

Run `make test`.

For ad-hoc testing, `socat -d -d pty,raw,echo=0 pty,raw,echo=0` can be useful to connect two virtual serial devices.
If a physical serial device exists, connect with `screen /dev/<device_name> [<baud_rate>]` where `<baud_rate>` is likely 115200.
