#!/usr/bin/env python

import logging
import subprocess

logging.basicConfig(level=logging.INFO)

# load kernel modules
subprocess.run(['modprobe', 'mac80211_hwsim', 'radios=32'], check=True)
subprocess.run(['modprobe', 'uleds'], check=True)
subprocess.run(['modprobe', 'ledtrig-netdev'], check=True)


import os; print(os.getcwd())
import node_manager
from os import geteuid


if geteuid() != 0:
    raise PermissionError('This script must be run as root')

# create environment
terrain = node_manager.Terrain()
medium = node_manager.WirelessMedium(terrain=terrain)

# create a router
r1 = node_manager.Router('test1')
r2 = node_manager.Router('test2')
r3 = node_manager.Router('test3')

# combine
medium.add(r1, (0, 0))
medium.add(r2, (100, 50))
medium.add(r3, (20, 49))

# drop to ipython console
from IPython import embed
embed()
