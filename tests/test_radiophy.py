import unittest
from ..node_manager import RadioPhy
from os.path import exists
from subprocess import run, Popen, PIPE
from time import sleep


class TestRadioPhy(unittest.TestCase):
    
    def test_create_from_any(self):
        phy = RadioPhy.from_any()
        self.assertTrue(exists(f'/sys/class/ieee80211/{phy.phy}'), 'PHY does not actually exist!')
        return
    
    def test_bind_unbind(self):
        phy = RadioPhy.from_any()

        # create new dummy network namespace, using cat as placeholder program
        dummyprog = Popen(['/usr/bin/unshare', '--mount', '--net', '/usr/bin/sleep', '10'])
        dummypid = dummyprog.pid
        sleep(0.1)  # hope for unshare to finish

        phy.bind(dummypid)
        self.assertTrue(phy.isbound(), 'PHY is not bound when it supposed to be bound!')
        self.assertEqual(phy.netns_pid, dummypid, 'PHY is bound to wrong network namespace!')

        # physical check
        run(['/usr/bin/nsenter', '-t', str(dummypid), '-m', '-n', '/usr/bin/mount', '-t', 'sysfs', 'sysfs', '/sys'], check=True)
        run(['/usr/bin/nsenter', '-t', str(dummypid), '-m', '-n', '/usr/bin/iw', 'phy', phy.phy, 'info'], check=True)

        phy.unbind()
        self.assertFalse(phy.isbound(), 'PHY is bound when it supposed to be unbound!')

        dummyprog.kill()
        return
        