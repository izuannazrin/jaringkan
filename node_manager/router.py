# Dengan nama Allah yang maha pemurah lagi maha penyayang
# Semoga projek ni cepat siap and menjadi aminnnn AHAHAHAHAHAHAH

import atexit
from os import set_blocking, path, listdir, kill as kill_pid
import struct
import subprocess
from docker import DockerClient
from docker.models.containers import Container
from docker.types import Mount
from random import randint
from requests.exceptions import ReadTimeout
import logging
from .radio import RadioPhy
from .linuxutils import Namespace, mount

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


class Router:
    _dockclt: DockerClient
    container: Container
    hostname: str

    _led_power: ULed
    _led_wan: ULed
    _led_lan: ULed
    _led_wlan: ULed
    _radio: RadioPhy

    _running_ns: Namespace

    def __init__(self, hostname:str = None, docker_connection: None|str|DockerClient = None):
        if isinstance(docker_connection, str) or docker_connection is None:
            self._dockclt = DockerClient(docker_connection)
        elif isinstance(docker_connection, DockerClient):
            self._dockclt = docker_connection
        else:
            raise TypeError(f"docker_connection must be str or DockerClient, not {type(docker_connection)}")
        
        self.container = None
        self._running_ns = None
        
        if hostname is None:
            # hostname not provided, autogenerate 6 characters
            hostname = f'{randint(0x100000, 0xffffff):x}'
        self.hostname = hostname
        
        # create leds
        self._led_power = ULed(f'jk-{self.hostname}:green:power')
        self._led_lan = ULed(f'jk-{self.hostname}:green:lan')
        self._led_wan = ULed(f'jk-{self.hostname}:green:wan')
        self._led_wlan = ULed(f'jk-{self.hostname}:green:wlan')

        # create radio
        self._radio = RadioPhy()

        # create docker container
        self.container = self._dockclt.containers.create(
            'jaringkan-openwrt:latest',
            cap_add=['NET_ADMIN'],
            hostname=self.hostname,
            mem_limit='128m',
            mounts=[
                Mount('/tmp', None, type='tmpfs', tmpfs_size='128m', tmpfs_mode=0o777)
            ],
            name='jk-' + self.hostname,
            network_mode='bridge',  # for wan interface
            tty=True,
        )
        
        # register atexit
        atexit.register(self.__del__)
    
    def __del__(self):
        if self.container:
            try:
                self.stop()
            except Exception as e:
                # log.warning(f"Failed to stop router {self.hostname}: {e}")
                pass
            self.container.remove()

    def __repr__(self):
        return f'<Router hostname={self.hostname!r} {self.status}>'
    
    def _create_veth(self):
        subprocess.run(['/usr/bin/ip', 'link', 'add', f'vjk-{self.hostname[:8]}', 'type', 'veth', 'peer', 'name', f'vjkp{self.hostname[:8]}'], check=True)
        subprocess.run(['/usr/bin/ip', 'link', 'set', f'vjkp{self.hostname[:8]}', 'netns', str(self.container.attrs['State']['Pid'])], check=True)
        # subprocess.run(['/usr/bin/nsenter', '-t', str(self.container.attrs['State']['Pid']), '-n', '/usr/bin/ip', 'link', 'set', f'vjkp{self._hostname[:8]}', 'name', 'eth1'], check=True)
        with Namespace(net=self.container.attrs['State']['Pid']):
            subprocess.run(['/usr/bin/ip', 'link', 'set', f'vjkp{self.hostname[:8]}', 'name', 'eth1'], check=True)
            subprocess.run(['/usr/bin/ip', 'link', 'set', 'eth1', 'down'], check=True)

    def _remove_veth(self):
        try:
            subprocess.run(['/usr/bin/ip', 'link', 'del', f'vjk-{self.hostname[:8]}'], check=True)
        except subprocess.CalledProcessError as e:
            log.warning(f"Failed to remove veth: {e}")
            pass

    def _on_stop(self):
        self._remove_veth()
        try:
            self._radio.unbind()
        except Exception as e:
            log.warning(f"Failed to unbind radio: {e}")
            pass
        self._led_power.brightness = 0
        self._led_lan.brightness = 0
        self._led_wan.brightness = 0
        self._led_wlan.brightness = 0
    
    @property
    def status(self):
        self.container.reload()
        if hasattr(self, '_status') and self._status == 'running' and self.container.status == 'exited':
            self._on_stop()
        self._status = self.container.status
        return self.container.status
    
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

        self.container.start()
        self.container.reload()
        pid = self.container.attrs['State']['Pid']
        log.info(f"Router {self.hostname} started with PID {pid}")

        # wait for container waitlock
        wait_result = self.container.exec_run('''/bin/sh -c "
            for i in 1 2 3; do
                if [ -e /tmp/.wait-for-host ]; then
                    exit 0
                fi
                sleep 1
            done; exit 1
        "''')
        if wait_result[0] != 0:
            log.warning(f"Timed out waiting for container to be ready for host. Continuing with initialization.")

        # create lan port
        self._create_veth()

        # bind radio to container
        self._radio.bind(pid)

        # bind mount leds to read-write
        with Namespace(mnt=pid):
            for ledname in [self._led_power.name, self._led_wan.name, self._led_lan.name, self._led_wlan.name]:
                mount(f'/sys/class/leds/{ledname}', f'/sys/class/leds/{ledname}', None, None, bind=True)    # bind mount
                mount(None, f'/sys/class/leds/{ledname}', None, None, remount=True)     # remount read-write

        # done. remove waitlock from container
        self.container.exec_run('rm -f /tmp/.wait-for-host')

    def pause(self):
        self.container.pause()

    def unpause(self):
        self.container.unpause()

    def stop(self):
        if self.status != 'running':
            return
        
        log.info(f"Stopping router {self.hostname}...")
        self.container.stop(timeout=10)
        self.container.reload()
        if self.container.attrs['State']['ExitCode'] != 0:
            log.warning(f"Container stopped with non-zero code {self.container.attrs['State']['ExitCode']}")
        self._on_stop()
