import sys
sys.path.append('..')

from wmediumd_py.wmediumd.wmediumdPyConnector import WmediumdStarter, WmediumdConstants, WmediumdManager, WmediumdIntfRef, WmediumdERRPROBLink
from .router import Router
import atexit


class Terrain:
    _terrain_map: any
    _air_permeability: float
    _land_permeability: float

    def __init__(self):
        # self._terrain_map = None      # TODO: terrain map 2d matrix
        self._air_permeability = 1.0    # Default 100%
        self._land_permeability = 1.0

    def get_strength(self, coord_1: tuple[float, float], coord_2: tuple[float, float]):
        # TODO: Loop each pythagorean distance and calculate signal strength
        return self._air_permeability * 1.0


class WirelessMedium:
    _terrain: Terrain
    _intf: dict[Router, WmediumdIntfRef]
    _coords: dict[Router, tuple[float, float]]
    _signals: dict[Router, dict[Router, float]]
    
    def __init__(self, terrain: Terrain = None):
        self._terrain = terrain
        self._intf = {}
        self._coords = {}
        self._signals = {}

        WmediumdStarter.initialize(executable='./wmediumd/wmediumd/wmediumd', parameters=['-l', '5'], mode=WmediumdConstants.WMEDIUMD_MODE_ERRPROB)
        WmediumdStarter.start()
        WmediumdManager.connect()

        atexit.register(self.__del__)

    def __del__(self):
        if WmediumdStarter.is_connected:
            WmediumdStarter.stop()

    def _get_routers(self):
        routers = set(self._intf.keys())
        return routers
    
    def _update_signal(self, router: Router):
        routers = self._get_routers()
        routers.remove(router)

        for r in routers:
            if self._terrain:
                signal = self._terrain.get_strength(self._coords[router], self._coords[r])
            else:
                signal = 10

            self._signals[router][r] = signal
            self._signals[r][router] = signal

            errprob = WmediumdERRPROBLink(self._intf[router], self._intf[r], 1.0-signal)
            WmediumdManager.update_link_errprob(errprob)

    def attach_terrain(self, terrain: Terrain):
        self._terrain = terrain

        # Kemaskini kekuatan signal untuk setiap router
        routers = self._get_routers()
        for router in routers:
            self._update_signal(router)

    def add(self, router: Router, coord: tuple[float, float]):
        if not isinstance(router, Router):
            raise ValueError("router must be an instance of Router")
        elif not isinstance(coord, tuple) or len(coord) != 2:
            raise ValueError("coord must be a tuple of size 2")
        
        if router in self._intf:
            raise ValueError("Router {} already exists")
        
        self._coords[router] = coord
        self._intf[router] = WmediumdIntfRef(intfmac=router._radio.macaddr, staname=None, intfname=None)
        self._signals[router] = {router: r for r in self._get_routers() if r != router}
        WmediumdManager.register_interface(router._radio.macaddr)

        # Kemaskini kekuatan signal untuk router baru
        self._update_signal(router)

    def remove(self, router: Router):
        if not isinstance(router, Router):
            raise ValueError("router must be an instance of Router")
        
        if router not in self._router_intf:
            raise ValueError("Router {} does not exist")
        
        del self._intf[router]
        del self._coords[router]
        del self._signals[router]
        WmediumdManager.unregister_interface(router._radio.macaddr)
        
        # Buang dari router lain
        routers = self._get_routers()
        for r in routers:
            del self._signals[r][router]

    def move(self, router: Router, coord: tuple[float, float]):
        if not isinstance(router, Router):
            raise ValueError("router must be an instance of Router")
        elif not isinstance(coord, tuple) or len(coord) != 2:
            raise ValueError("coord must be a tuple of size 2")
        
        if router not in self._router_intf:
            raise ValueError("Router {} does not exist")
        
        self._coords[router] = coord

        # Kemaskini kekuatan signal untuk router yang bergerak
        self._update_signal(router)
