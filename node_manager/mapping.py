from io import TextIOBase
from .router import Router
from .radio import PhyManagement
import atexit
from .wmediumd import Wmediumd, WmediumdConfigPathLoss
from tempfile import NamedTemporaryFile

import logging
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class WirelessMedium:
    _wmd = Wmediumd()

    _coords: dict[Router, tuple[float, float]]
    _dirty: bool
    _wmdconfig_file: TextIOBase
    
    def __init__(self):
        self._coords = {}

        self._wmdconfig_file = NamedTemporaryFile('w', delete=False, prefix='jk_wmd_', suffix='.conf')

        atexit.register(self.__del__)

    def __del__(self):
        pass

    def _get_routers(self):
        return self._coords.keys()
    
    def commit(self):
        if self._dirty is False:
            return
        elif len(self._coords) < 1:
            return
        
        wmdconfig = WmediumdConfigPathLoss(3.5, 0.0)
        for router, coord in self._coords.items():
            wmdconfig.add(router._radio.macaddr, coord[0], coord[1], 10.0)
        
        self._wmdconfig_file.seek(0)
        self._wmdconfig_file.truncate(0)
        wmdconfig.export(self._wmdconfig_file)
        self._wmdconfig_file.flush()
        
        Wmediumd.stop()
        Wmediumd.start(self._wmdconfig_file.name, ns_fd=PhyManagement.stub_ns.net)

    def add(self, router: Router, x: float, y: float):
        self._dirty = True
        self._coords[router] = (x, y)

    def remove(self, router: Router):
        self._dirty = True
        del self._coords[router]

    def move(self, router: Router, coord: tuple[float, float]):
        self._dirty = True
        self._coords[router] = coord
