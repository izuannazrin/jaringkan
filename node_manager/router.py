# Dengan nama Allah yang maha pemurah lagi maha penyayang
# Semoga projek ni cepat siap and menjadi aminnnn AHAHAHAHAHAHAH

import atexit
from os import set_blocking, path, listdir
import struct
import subprocess
from docker import DockerClient
from docker.models.containers import Container
from docker.types import Mount
from random import randint
from requests.exceptions import ReadTimeout
import logging

log = logging.getLogger(__name__)


class ULed:
    '''
    Userspace LED.

    Usage example:
    >>> new_led = ULed('testbed:white:blink')
    >>> print(new_led.brightness)

    `testbed:white:blink` will then controlled by kernel LED triggers such as blink or netdev.
    Brightness of 0 means LED is off, 1 means LED is on.
    '''
    max_brightness = 1
    
    name: str
    _brightness: int

    def __init__(self, led_name: str):
        # check if kernel module is loaded
        if not path.exists('/dev/uleds'):
            raise OSError('Linux kernel module uleds not loaded!')

        # NOTE: opening file handle, then sending struct, then kernel will create LED device
        self._dev_hnd = open('/dev/uleds', 'r+b', buffering=0)
        set_blocking(self._dev_hnd.fileno(), False)

        # NOTE: Refer to /usr/include/linux/uleds.h for uleds_user_dev structure
        struct_ledname = struct.pack('64si', led_name.encode('ascii'), self.max_brightness)
        self._dev_hnd.write(struct_ledname)

        self.name = led_name

    def __del__(self):
        # NOTE: closing file handle will destroy LED device from kernel
        if hasattr(self, '_dev_hnd'):
            self._dev_hnd.close()

    def __repr__(self):
        return f'<ULeds {self.name!r}>'
    
    @property
    def brightness(self):
        recvbuf = self._dev_hnd.read(4)
        if recvbuf is None:
            return self._brightness
        
        self._brightness = struct.unpack('i', recvbuf)[0]
        return self._brightness
    
    @brightness.setter
    def brightness(self, brightness: int):
        if not isinstance(brightness, int):
            raise TypeError(f'Expected int, got {type(brightness)}')

        with open(f'/sys/class/leds/{self.name}/brightness', 'w') as f:
            f.write(str(brightness))
        self._brightness = brightness


class RadioPhy:
    '''
    PHY interfaces for mac80211_hwsim.
    Contains everything you need to control the PHY, such as binding to network namespace, etc.
    '''
    # _hwsim: str
    __phylist = []

    _phy: str
    _macaddr: str
    _netns_pid: int | None

    def __init__(self, phyname):
        if not path.exists(f'/sys/class/ieee80211/{phyname}'):
            raise ValueError(f'PHY {phyname} does not exist!')
        if not path.realpath(f'/sys/class/ieee80211/{phyname}/device').startswith('/sys/devices/virtual/mac80211_hwsim/'):
            raise ValueError(f'PHY {phyname} is not part of mac80211_hwsim!')

        RadioPhy.__phylist.append(phyname)
        self._phy = phyname
        self._netns_pid = None

        # get MAC address
        with open(f'/sys/class/ieee80211/{phyname}/macaddress', 'r') as f:
            self._macaddr = f.read().strip()

    def __del__(self):
        RadioPhy.__phylist.remove(self._phy)
    
    def __repr__(self):
        if self._netns_pid:
            bound_str = f'bound to {self._netns_pid}'
        else:
            bound_str = 'not bound'
        return f'<RadioPhy {self._phy} {bound_str}>'

    @property
    def phy(self):
        return self._phy

    @property
    def macaddr(self):
        return self._macaddr

    @property
    def netns_pid(self):
        if path.exists(f'/sys/class/ieee80211/{self._phy}'):
            # phy is owned by root netns
            if self._netns_pid is not None:
                raise RuntimeError(f'PHY {self._phy} kernel state inconsistent with object state!')
            return None

        else:
            # phy is owned by some network namespace
            if self._netns_pid is None:
                raise RuntimeError(f'PHY {self._phy} kernel state inconsistent with object state!')
            return self._netns_pid
    
    def isbound(self):
        return self.netns_pid is not None
    
    def bind(self, netns_pid: int):
        if self._netns_pid:
            raise ValueError(f'PHY {self._phy} is already bound to network namespace of PID {self._netns_pid}!')

        log.info(f'Binding PHY {self._phy} to network namespace of PID {netns_pid}...')
        subprocess.run(['/usr/bin/iw', 'phy', self._phy, 'set', 'netns', str(netns_pid)], check=True)
        # from time import sleep; sleep(10)

        if path.exists(f'/sys/class/ieee80211/{self._phy}'):
            raise NotImplementedError(f'PHY {self._phy} is still bound to root network namespace, which is unsupported!')
        
        self._netns_pid = netns_pid
    
    def unbind(self):
        if path.exists(f'/sys/class/ieee80211/{self._phy}'):
            # phy is now owned by root netns, perhaps by the destruction of its network namespace
            self._netns_pid = None
            return

        # phy is still owned by some network namespace
        # enter netns, then move phy to root netns
        subprocess.run(['/usr/bin/nsenter', '-t', str(self._netns_pid), '-m', '-n', '/usr/bin/iw', 'phy', self._phy, 'set', 'netns', '1'], check=True)
        self._netns_pid = None

    @staticmethod
    def from_any():
        if not path.exists('/sys/devices/virtual/mac80211_hwsim'):
            raise OSError('Linux kernel module mac80211_hwsim not loaded!')

        hwsims = listdir('/sys/devices/virtual/mac80211_hwsim')
        for hwsim in hwsims:
            phys = listdir(f'/sys/devices/virtual/mac80211_hwsim/{hwsim}/ieee80211')
            if phys and phys not in RadioPhy.__phylist:
                return RadioPhy(phys[0])
                # TODO: what if there are multiple calls to from_any() before the first one is bound?

        raise ValueError('No available PHYs found in mac80211_hwsim!')


class Router:
    _dockclt: DockerClient
    _container: Container

    _led_power: ULed
    _led_wan: ULed
    _led_lan: ULed
    _led_wlan: ULed
    _radio: RadioPhy

    def __init__(self, hostname:str = None, docker_connection: None|str|DockerClient = None):
        if isinstance(docker_connection, str) or docker_connection is None:
            self._dockclt = DockerClient(docker_connection)
        elif isinstance(docker_connection, DockerClient):
            self._dockclt = docker_connection
        else:
            raise TypeError(f'docker_connection must be str or DockerClient, not {type(docker_connection)}')
        
        if hostname is None:
            # hostname not provided, autogenerate 6 characters
            hostname = hex(randint(0x100000, 0xffffff)).lstrip('0x')
        self._hostname = hostname
        
        # create leds
        self._led_power = ULed(f'jk-{self._hostname}:green:power')
        self._led_lan = ULed(f'jk-{self._hostname}:green:lan')
        self._led_wan = ULed(f'jk-{self._hostname}:green:wan')
        self._led_wlan = ULed(f'jk-{self._hostname}:green:wlan')

        # create radio
        self._radio = RadioPhy.from_any()

        # create docker container
        self._container = self._dockclt.containers.create(
            'jaringkan-openwrt:latest',
            cap_add=['NET_ADMIN'],
            hostname=self._hostname,
            mem_limit='128m',
            mounts=[
                Mount('/tmp', None, type='tmpfs', tmpfs_size='128m', tmpfs_mode=0o777)
            ],
            name='jk-' + self._hostname,
            network_mode='none',
            tty=True,
        )
        
        # register atexit
        atexit.register(self.__del__)
    
    def __del__(self):
        if hasattr(self, '_container') and self._container:
            self.stop()
            self._container.remove()
            self._container = None

    def __repr__(self):
        return f'<Router hostname={self._hostname!r}>'

    def _on_stop(self):
        self._radio.unbind()
        self._led_power.brightness = 0
        self._led_lan.brightness = 0
        self._led_wan.brightness = 0
        self._led_wlan.brightness = 0
    
    @property
    def status(self):
        self._container.reload()
        if hasattr(self, '_status') and self._status == 'running' and self._container.status == 'exited':
            self._on_stop()
        self._status = self._container.status
        return self._container.status
    
    def get_leds(self):
        return {
            'power': self._led_power.brightness,
            'wan': self._led_wan.brightness,
            'lan': self._led_lan.brightness,
            'wlan': self._led_wlan.brightness
        }
    
    def start(self):
        if self.status == 'running':
            return

        self._container.start()
        self._container.reload()
        pid = self._container.attrs['State']['Pid']

        # wait for container waitlock
        wait_result = self._container.exec_run('''/bin/sh -c "
            for i in 1 2 3; do
                if [ -e /tmp/.wait-for-host ]; then
                    exit 0
                fi
                sleep 1
            done; exit 1
        "''')
        if wait_result[0] != 0:
            log.warning(f'Timed out waiting for container to be ready for host. Continuing with initialization.')

        # bind radio to container
        self._radio.bind(pid)

        # bind mount leds to read-write
        for ledname in [self._led_power.name, self._led_wan.name, self._led_lan.name, self._led_wlan.name]:
            subprocess.run(['/usr/bin/nsenter', '-t', str(pid), '-m', '/usr/bin/mount', '--bind', f'/sys/class/leds/{ledname}', f'/sys/class/leds/{ledname}'], check=True)
            subprocess.run(['/usr/bin/nsenter', '-t', str(pid), '-m', '/usr/bin/mount', '-o', 'remount,rw', f'/sys/class/leds/{ledname}'], check=True)

        # done. remove waitlock from container
        self._container.exec_run('rm -f /tmp/.wait-for-host')

    def pause(self):
        self._container.pause()

    def unpause(self):
        self._container.unpause()

    def stop(self):
        self._container.stop(timeout=10)
        self._container.reload()
        if self._container.attrs['State']['ExitCode'] != 0:
            log.warning(f'Container stopped with non-zero code {self._container.attrs["State"]["ExitCode"]}')
        self._on_stop()
