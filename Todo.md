[x] ULed issue with reading realtime brightness, read returned None if nothing happened

[x] Router.__del__ fail to stop container due to dockerpy and urllib.parse.quote issue. issue when closing python
    [x] partial fix

[x] Router.start should handle attaching phy and making sure container startup is well

[ ] closing run.py errors:
        Exception ignored in: <function Router.__del__ at 0x7023c06f1b20>
        Traceback (most recent call last):
        File "/home/izuan/code/jaringkan/node_manager/router.py", line 138, in __del__
        File "/usr/lib/python3.12/logging/__init__.py", line 1550, in warning
        File "/usr/lib/python3.12/logging/__init__.py", line 1800, in isEnabledFor
        TypeError: 'NoneType' object is not callable
        Exception ignored in: <function Router.__del__ at 0x7023c06f1b20>
        Traceback (most recent call last):
        File "/home/izuan/code/jaringkan/node_manager/router.py", line 138, in __del__
        File "/usr/lib/python3.12/logging/__init__.py", line 1550, in warning
        File "/usr/lib/python3.12/logging/__init__.py", line 1800, in isEnabledFor
        TypeError: 'NoneType' object is not callable
        Exception ignored in: <function Router.__del__ at 0x7023c06f1b20>
        Traceback (most recent call last):
        File "/home/izuan/code/jaringkan/node_manager/router.py", line 138, in __del__
        File "/usr/lib/python3.12/logging/__init__.py", line 1550, in warning
        File "/usr/lib/python3.12/logging/__init__.py", line 1800, in isEnabledFor
        TypeError: 'NoneType' object is not callable

    {in another instance}
        INFO:node_manager.router:Stopping router test1...

        W_SRV: shutting down wserver
        Exception ignored in: <function Router.__del__ at 0x7c124c9bdc60>
        Traceback (most recent call last):
        File "/home/izuan/code/jaringkan/node_manager/router.py", line 138, in __del__
        File "/usr/lib/python3.12/logging/__init__.py", line 1550, in warning
        File "/usr/lib/python3.12/logging/__init__.py", line 1800, in isEnabledFor
        TypeError: 'NoneType' object is not callable
        Exception ignored in: <function Router.__del__ at 0x7c124c9bdc60>
        Traceback (most recent call last):
        File "/home/izuan/code/jaringkan/node_manager/router.py", line 138, in __del__
        File "/usr/lib/python3.12/logging/__init__.py", line 1550, in warning
        File "/usr/lib/python3.12/logging/__init__.py", line 1800, in isEnabledFor
        TypeError: 'NoneType' object is not callable
        Exception ignored in: <function Router.__del__ at 0x7c124c9bdc60>
        Traceback (most recent call last):
        File "/home/izuan/code/jaringkan/node_manager/router.py", line 138, in __del__
        File "/usr/lib/python3.12/logging/__init__.py", line 1550, in warning
        File "/usr/lib/python3.12/logging/__init__.py", line 1800, in isEnabledFor
        TypeError: 'NoneType' object is not callable

[ ] occasional error about:
        WARNING:node_manager.router:Failed to remove veth: Command '['/usr/bin/ip', 'link', 'del', 'vjk-test2']' returned non-zero exit status 1.
        INFO:node_manager.router:Router test2 started with PID 187890
        INFO:node_manager.radio:{self}: (Re-)mounting sysfs for target netns...

    -or-

        In [7]: r2.start()
        INFO:node_manager.router:Router test2 started with PID 179511
        INFO:node_manager.radio:{self}: (Re-)mounting sysfs for target netns...

        In [8]: r2.start()
        INFO:node_manager.router:Router test2 started with PID 183375
        RTNETLINK answers: File exists
        --------------------------------------------------------------
        CalledProcessError           Traceback (most recent call last)
        Cell In[8], line 1
        ----> 1 r2.start()

        File /home/izuan/code/jaringkan/node_manager/router.py:210, in Router.start(self)
            207     log.warning(f"Timed out waiting for container to be ready for host. Continuing with initialization.")
            209 # create lan port
        --> 210 self._create_veth()
            212 # bind radio to container
            213 self._radio.bind(pid)

        File /home/izuan/code/jaringkan/node_manager/router.py:146, in Router._create_veth(self)
            145 def _create_veth(self):
        --> 146     subprocess.run(['/usr/bin/ip', 'link', 'add', f'vjk-{self.hostname[:8]}', 'type', 'veth', 'peer', 'name', f'vjkp{self.hostname[:8]}'], check=True)
            147     subprocess.run(['/usr/bin/ip', 'link', 'set', f'vjkp{self.hostname[:8]}', 'netns', str(self.container.attrs['State']['Pid'])], check=True)
            148     # subprocess.run(['/usr/bin/nsenter', '-t', str(self.container.attrs['State']['Pid']), '-n', '/usr/bin/ip', 'link', 'set', f'vjkp{self._hostname[:8]}', 'name', 'eth1'], check=True)

        File /usr/lib/python3.12/subprocess.py:571, in run(input, capture_output, timeout, check, *popenargs, **kwargs)
            569     retcode = process.poll()
            570     if check and retcode:
        --> 571         raise CalledProcessError(retcode, process.args,
            572                                  output=stdout, stderr=stderr)
            573 return CompletedProcess(process.args, retcode, stdout, stderr)

        CalledProcessError: Command '['/usr/bin/ip', 'link', 'add', 'vjk-test2', 'type', 'veth', 'peer', 'name', 'vjkptest2']' returned non-zero exit status 2.