#!/usr/bin/env python

import node_manager
import subprocess


# load kernel modules
subprocess.run(['sudo', 'modprobe', 'mac80211_hwsim', 'radios=32'])
subprocess.run(['sudo', 'modprobe', 'uleds'])

# create a router
r = node_manager.Router('test1')

# drop to ipython console
from IPython import embed
embed()