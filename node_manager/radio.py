# Trivia: When moving PHY to another netns, even when nsenter-ing into the netns,
#         sysfs won't show the entry for the moved PHY.
#         This is because sysfs mounts have its own namespace tag.
#         To see the PHY in sysfs, we need to create a new mount namespace and remount sysfs.


from os import listdir
import logging
from subprocess import run
import subprocess
from .linuxutils import Namespace, mount


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class PhyManagement:

    tool_mgmt = 'mac80211_hwsim_mgmt/hwsim_mgmt/hwsim_mgmt'
    initialized = False
    stub_ns: Namespace
    popped_phy: set[str] = set()

    @classmethod
    def _hwsim_mgmt_add(cls):
        with cls.stub_ns:
            process = run([cls.tool_mgmt, '-c'], stdout=subprocess.PIPE, check=True)
            
            hwsim_id = process.stdout.decode().split()[-1]
            hwsim_id = int(hwsim_id)

            hwsim = f'hwsim{hwsim_id}'
            phys = listdir(f'/sys/devices/virtual/mac80211_hwsim/{hwsim}/ieee80211')
            if len(phys) == 0:
                raise RuntimeError('No PHY found in newly created hwsim!')
        
            return (hwsim, phys[0])
    
    @classmethod
    def _prepare_ns(cls):
        # if getattr(cls, 'stub_ns', None):
        #     log.warning("Stub namespace already created! Are you reloading?")
        #     return

        cls.stub_ns = Namespace(mnt=True, net=True)
        with cls.stub_ns:
            mount(None, '/', None, None, propagation='rprivate')    # change propagation
            mount('sysfs', '/sys', 'sysfs', None)                   # in-place mount sysfs

    @classmethod
    def _iter_unused_phy(cls):
        try:
            hwsims = listdir('/sys/devices/virtual/mac80211_hwsim')
            for hwsim in hwsims:
                phys = listdir(f'/sys/devices/virtual/mac80211_hwsim/{hwsim}/ieee80211')
                for phy in phys:
                    if phy in cls.popped_phy:
                        continue
                    yield (hwsim, phy)
        except FileNotFoundError:
            pass

    @classmethod
    def prepare(cls):
        # if not path.exists('/sys/devices/virtual/mac80211_hwsim'):
        #     raise RuntimeError('Linux kernel module mac80211_hwsim not loaded!')
        
        cls._prepare_ns()

    @classmethod
    def pop(cls):
        try:
            hwsim, phy = next(cls._iter_unused_phy())
            log.debug(f"Popped PHY from unused pile: {phy}")
        except StopIteration:
            hwsim, phy = cls._hwsim_mgmt_add()
            log.debug(f"Popped PHY from newly created hwsim: {phy}")

        cls.popped_phy.add(phy)
        return (hwsim, phy)
    
    @classmethod
    def push(cls, phy: str):
        cls.popped_phy.add(phy[1])

PhyManagement.prepare()


class RadioPhy:
    '''
    PHY interfaces for mac80211_hwsim.
    Contains everything you need to control the PHY, such as binding to network namespace, etc.
    '''

    _hwsim: str
    _phy: str
    _macaddr: str

    origin_netns: Namespace
    target_netns: Namespace | None

    def __init__(self):
        self._hwsim, self._phy = PhyManagement.pop()
        self._origin_netns = PhyManagement.stub_ns
        self._target_netns = None

        # get MAC address
        with self._origin_netns:
            import os; print(os.listdir('/sys/class/ieee80211'))
            with open(f'/sys/class/ieee80211/{self._phy}/macaddress') as f:
                self._macaddr = f.read().strip()

    def __del__(self):
        try:
            self.unbind()
        except Exception as e:
            # log.error(f"{self}: __del__: Failed to unbind PHY {self._phy}: {e}")
            pass
        PhyManagement.push(self._phy)
    
    def __repr__(self):
        bound_str = f'bound' if self._target_netns else 'not bound'
        return f'<RadioPhy {self._phy} {bound_str}>'

    @property
    def macaddr(self):
        return self._macaddr
    
    def isbound(self):
        return self._target_netns is not None
    
    def bind(self, netns_pid: int):
        if self.isbound():
            raise ValueError(f"PHY {self._phy} is already bound!")
        
        self._target_netns = Namespace(net=netns_pid, mnt=True)
        with self._target_netns:
            mount(None, '/', None, None, propagation='rprivate')
            mount('sysfs', '/sys', 'sysfs', None)

        # move from origin to target netns
        with self._origin_netns:
            run(['/usr/bin/iw', 'phy', self._phy, 'set', 'netns', 'name', f'/proc/self/fd/{self._target_netns.net}'], pass_fds=[self._target_netns.net], check=True)
    
    def unbind(self):
        if not self.isbound():
            return
        
        # return to original netns
        with self._target_netns:
            run(['/usr/bin/iw', 'phy', self._phy, 'set', 'netns', 'name', f'/proc/self/fd/{self._origin_netns.net}'], pass_fds=[self._origin_netns.net], check=True)

        self._target_netns = None
        # TODO: check if by setting self._netns = None, __del__ will be called. Otherwise potential leak
        log.warning(f"{self}: unbind(): Please check if {self._target_netns} is destroyed after this!")
