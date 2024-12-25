# Trivia: When moving PHY to another netns, even when nsenter-ing into the netns,
#         sysfs won't show the entry for the moved PHY.
#         This is because sysfs mounts have its own namespace tag.
#         To see the PHY in sysfs, we need to create a new mount namespace and remount sysfs.


from os import path, kill as kill_pid, listdir
import logging
from subprocess import run
from .linuxutils import Namespace, mount


log = logging.getLogger(__name__)


class PhyManagement:

    stub_ns: Namespace
    phys: set[str] = set()

    @classmethod
    def _prepare(cls):
        if not path.exists('/sys/devices/virtual/mac80211_hwsim'):
            raise OSError('Linux kernel module mac80211_hwsim not loaded!')
        
        # prepare stub namespace
        cls.stub_ns = Namespace(net=True, mnt=True)
        with cls.stub_ns:
            log.info('(Re-)mounting sysfs...')
            mount(None, '/', None, None, propagation='rprivate')
            mount('sysfs', '/sys', 'sysfs', None)
        
        # insert all mac80211_hwsim phy from root to stub namespace
        hwsims = listdir('/sys/devices/virtual/mac80211_hwsim')
        for hwsim in hwsims:
            phys = listdir(f'/sys/devices/virtual/mac80211_hwsim/{hwsim}/ieee80211')
            for phy in phys:
                cls.phys.add(phy)
                # run(['/bin/ls', '-l', f'/proc/self/fd'], pass_fds=[cls.stub_ns.net], check=True)
                run(['/usr/bin/iw', 'phy', phy, 'set', 'netns', 'name', f'/proc/self/fd/{cls.stub_ns.net}'], pass_fds=[cls.stub_ns.net], check=True)

        if len(cls.phys) == 0:
            raise OSError('No mac80211_hwsim PHY found!')

    @classmethod
    def pop(cls):
        return cls.phys.pop()
    
    @classmethod
    def push(cls, phy: str):
        cls.phys.add(phy)

PhyManagement._prepare()


class RadioPhy:
    '''
    PHY interfaces for mac80211_hwsim.
    Contains everything you need to control the PHY, such as binding to network namespace, etc.
    '''

    _phy: str
    _macaddr: str
    _origin_netns: Namespace
    _target_netns: Namespace | None

    def __init__(self):
        self._phy = PhyManagement.pop()
        self._origin_netns = PhyManagement.stub_ns
        self._target_netns = None

        # get MAC address
        with self._origin_netns:
            import os; print(os.listdir('/sys/class/ieee80211'))
            with open(f'/sys/class/ieee80211/{self._phy}/macaddress') as f:
                self._macaddr = f.read().strip()

    def __del__(self):
        self.unbind()
        PhyManagement.push(self._phy)
    
    def __repr__(self):
        bound_str = f'bound' if self._target_netns else 'not bound'
        return f'<RadioPhy {self._phy} {bound_str}>'

    @property
    def phy(self):
        return self._phy

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
            log.info("{self}: (Re-)mounting sysfs for target netns...")
            mount(None, '/', None, None, propagation='rprivate')
            mount('sysfs', '/sys', 'sysfs', None)

        # move from origin to target netns
        with self._origin_netns:
            # run(['/bin/ls', '-l', f'/proc/self/fd'], pass_fds=[self._target_netns.net], check=True)
            run(['/usr/bin/iw', 'phy', self._phy, 'set', 'netns', 'name', f'/proc/self/fd/{self._target_netns.net}'], pass_fds=[self._target_netns.net], check=True)
    
    def unbind(self):
        if not self.isbound():
            return
        
        # return to original netns
        with self._target_netns:
            run(['/usr/bin/iw', 'phy', self._phy, 'set', 'netns', 'name', f'/proc/self/fd/{self._origin_netns.net}'], pass_fds=[self._origin_netns.net], check=True)

        self._target_netns = None
        # TODO: check if by setting self._netns = None, __del__ will be called. Otherwise potential leak
