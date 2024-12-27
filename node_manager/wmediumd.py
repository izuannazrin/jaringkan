from io import TextIOBase
from struct import Struct
# from os import setns, CLONE_NEWNET, open as open_fd
import os, sys
from socket import socket, AF_UNIX, SOCK_STREAM
from subprocess import Popen, run
from enum import IntEnum
from tempfile import mktemp
import atexit

import logging
import time
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class WmediumdMsgType(IntEnum):
    INVALID     = 0
    ACK         = 1
    REGISTER    = 2
    UNREGISTER  = 3
    NETLINK     = 4
    SET_CONTROL = 5
    TX_START    = 6


class WmediumdCtlType(IntEnum):
    NOTIFY_TX_START = 0
    RX_ALL_FRAMES   = 1


class Wmediumd:

    tool_wmediumd = 'wmediumd/wmediumd/wmediumd'
    _struct_header = Struct('@II')
    _struct_control = Struct('@I')
    _struct_tx_start = Struct('@QIxxx')

    _config_path: str = None
    _ns_fd: int | None = None
    _process: Popen = None
    _sock_api: socket = None

    @classmethod
    def _process_exec(cls, sock_api_path: str):
        run(['/bin/cat', cls._config_path], check=True)
        cls._process = Popen([cls.tool_wmediumd, '-l', '7', '-c', cls._config_path, '-a', sock_api_path], stdout=sys.stderr, stderr=sys.stderr)
        log.debug(f"Started wmediumd, config {cls._config_path}, socket path {sock_api_path}")

    @classmethod
    def _process_kill(cls, signal: int = None):
        cls._process.terminate()
        try:
            cls._process.wait(0.1)
        except TimeoutError:
            cls._process.kill()
            cls._process.wait()
        cls._process = None
        log.debug(f"Stopped wmediumd")

    @classmethod
    def _send(cls, msg_type, msg_data: bytes):
        if not cls._process:
            raise ValueError("wmediumd is not running")
        
        cls._sock_api.send(cls._struct_header.pack(msg_type, len(msg_data)) + msg_data)

        # wait for ACK
        response = cls._sock_api.recv(cls._struct_header.size)
        response_type, response_length = cls._struct_header.unpack(response)
        if response_length > 0:
            log.warning(f"Ignoring wmediumd_api ACK with data of length {response_length}")

        if response_type != WmediumdMsgType.ACK:
            raise ValueError(f"Expected wmediumd_api ACK, got {WmediumdMsgType(response_type).name if response_type in WmediumdMsgType else hex(response_type)}")
        
        log.debug(f"Received wmediumd_api ACK!")
    
    @classmethod
    def api_register(cls):
        return cls._send(WmediumdMsgType.REGISTER, b'')
    
    @classmethod
    def api_unregister(cls):
        return cls._send(WmediumdMsgType.UNREGISTER, b'')

    @classmethod
    def start(cls, config_path: str, ns_fd: int = None):
        cls._config_path = config_path
        cls._ns_fd = ns_fd

        if cls._process:
            # check if process is still running, otherwise close socket
            if cls._process.poll() is None:
                raise ValueError("wmediumd is already running")
            cls._sock_api.close()
        
        tmp_path = mktemp(prefix='jk_wmd_', suffix='.sock')

        orig_ns = None
        if ns_fd:
            # enter provided namespace
            orig_ns = os.open(f'/proc/self/ns/net', 0)
            os.setns(ns_fd, os.CLONE_NEWNET)
        try:
            cls._process_exec(tmp_path)
        finally:
            # restore namespace no matter what
            if orig_ns:
                os.setns(orig_ns, os.CLONE_NEWNET)
                os.close(orig_ns)

        # wait for wmediumd to complete startup
        time.sleep(0.1)

        try:
            cls._sock_api = socket(AF_UNIX, SOCK_STREAM)
            cls._sock_api.connect(tmp_path)
        except:
            cls._sock_api.close()
            cls._sock_api = None
            
            cls._process_kill()
            raise

        atexit.register(cls.stop)
        cls.api_register()

    @classmethod
    def stop(cls):
        if cls._sock_api:
            try:
                cls.api_unregister()
            except Exception as e:
                log.error(f"Failed to unregister wmediumd API: {e}")
                pass
            cls._sock_api.close()
            cls._sock_api = None

        if cls._process:
            cls._process_kill()

        atexit.unregister(cls.stop)

    @classmethod
    def restart(cls, config_path: str = None):
        cls.stop()
        cls.start(config_path or cls._config_path, cls._ns_fd)


class WmediumdConfig:

    ifaces: list[str]

    def __init__(self):
        self.ifaces = []

    def _export_model(self, out_file: TextIOBase):
        pass

    def add(self, macaddr: str):
        if macaddr in self.ifaces:
            raise ValueError(f"{macaddr!r} already exist")
        
        addr_parts = macaddr.split(':')
        if len(addr_parts) != 6 or any(len(part) != 2 for part in addr_parts) or any(char.lower() not in '0123456789abcdef' for part in addr_parts for char in part):
            raise ValueError(f"Invalid MAC address {macaddr}")
        self.ifaces.append(macaddr)

    def export(self, out_file: TextIOBase):
        out_file.write(f'ifaces :\n{{\n\tids = [\n')
        out_file.write(',\n'.join(f'\t\t"{iface}"' for iface in self.ifaces))
        out_file.write('\n\t];\n};\n')

        self._export_model(out_file)


class WmediumdConfigPathLoss(WmediumdConfig):

    positions: list[tuple[float, float]]
    tx_powers: list[float]

    def __init__(self, path_loss_exp: float, xg: float):
        self.path_loss_exp = path_loss_exp
        self.xg = xg
        self.positions = []
        self.tx_powers = []

        super().__init__()

    def _export_model(self, out_file: TextIOBase):
        out_file.write(f'model :\n{{\n\ttype = "path_loss";\n\tpositions = (\n')
        out_file.write(',\n'.join(f'\t\t({x}, {y})' for x, y in self.positions))
        out_file.write('\n\t);\n\ttx_powers = (' + ', '.join(f'{tx_power:.1f}' for tx_power in self.tx_powers) + ');\n')
        out_file.write(f'\n\tmodel_name = "log_distance";\n\tpath_loss_exp = {self.path_loss_exp:.1f};\n\txg = {self.xg:.1f};\n}};\n')

    def add(self, macaddr: str, pos_x: float, pos_y: float, tx_power: float):
        super().add(macaddr)
        self.positions.append((pos_x, pos_y))
        self.tx_powers.append(tx_power)
