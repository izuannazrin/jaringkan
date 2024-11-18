import unittest
from ..node_manager import ULed
from os.path import exists
from subprocess import run
from time import sleep


class TestULeds(unittest.TestCase):

    def setUp(self):
        if self._testMethodName == 'test_create_and_destroy': return
        self.uled = ULed('test:green:power')
        return
    
    def test_create_and_destroy(self):
        uled = ULed('test:green:power')
        self.assertTrue(exists('/sys/class/leds/test:green:power'), 'LED sysfs not created!')

        del uled
        self.assertFalse(exists('/sys/class/leds/test:green:power'), 'LED sysfs not removed!')

        return
    
    def test_set_brightness(self):
        with open('/sys/class/leds/test:green:power/brightness', 'w') as f:
            f.write('1')
        self.assertEqual(self.uled.brightness, 1, 'Wrong brightness value!')

        with open('/sys/class/leds/test:green:power/brightness', 'w') as f:
            f.write('0')
        self.assertEqual(self.uled.brightness, 0, 'Wrong brightness value!')

        return
    
    def test_set_trigger(self):
        # load timer trigger kernel module
        run(['/sbin/modprobe', 'ledtrig-timer'], check=True)
        
        with open('/sys/class/leds/test:green:power/trigger', 'w') as f:
            f.write('timer')
        with open('/sys/class/leds/test:green:power/delay_on', 'w') as f:
            f.write('100')
        with open('/sys/class/leds/test:green:power/delay_off', 'w') as f:
            f.write('100')

        current_brightness = self.uled.brightness
        sleep(0.1)
        self.assertNotEqual(self.uled.brightness, current_brightness, 'LED not blinking!')

        return