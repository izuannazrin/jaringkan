from typing import Iterable
import logging
import os
import ctypes, ctypes.util


log = logging.getLogger(__name__)
libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
libc.mount.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p)
libc.umount.argtypes = (ctypes.c_char_p, ctypes.c_ulong)


class Namespace:
    TYPES = frozenset(('ipc', 'mnt', 'net', 'pid', 'time', 'user', 'uts'))
    UNSHARE_FLAGS = {
        'ipc': os.CLONE_NEWIPC,
        'mnt': os.CLONE_NEWNS,
        'net': os.CLONE_NEWNET,
        'pid': os.CLONE_NEWPID,
        'time': os.CLONE_NEWTIME,
        'user': os.CLONE_NEWUSER,
        'uts': os.CLONE_NEWUTS
    }

    _nstarget: dict[str,tuple[str,int|str]]
    _fd: dict[str,int]
    _pre_enter_fd: dict[str,int]

    _mnt_cwd: str | None

    def __init__(self, **kwargs):
        self._nstarget = {}
        self._fd = {}
        self._pre_enter_fd = {}
        self._mnt_cwd = None

        anon_ns = []
        for t, target in kwargs.items():
            if t not in Namespace.TYPES:
                raise ValueError(f"Invalid namespace type '{t}'")
            
            if target is True:
                anon_ns.append(t)
            
            elif isinstance(target, int):     # PID
                self._fd[t] = os.open(f'/proc/{target}/ns/{t}', 0)
                self._nstarget[t] = ('pid', target)

            elif isinstance(target, str):   # absolute path
                self._fd[t] = os.open(target, 0)
                self._nstarget[t] = ('path', target)

            else:
                raise TypeError(f"Expected int or str, got {type(target)}")
            
        if anon_ns:
            for t in anon_ns:
                self._pre_enter_fd[t] = os.open(f'/proc/self/ns/{t}', 0)
            cwd = os.getcwd()

            os.unshare(sum(Namespace.UNSHARE_FLAGS[t] for t in anon_ns))
            for t in anon_ns:
                self._fd[t] = os.open(f'/proc/self/ns/{t}', 0)
                self._nstarget[t] = ('anon', os.readlink(f'/proc/self/ns/{t}'))
            
            if cwd != os.getcwd():
                log.debug(f"cwd does in fact change after unshare! {cwd} -> {os.getcwd()}")

            # restore namespace
            for t, fd in self._pre_enter_fd.items():
                os.setns(fd, Namespace.UNSHARE_FLAGS[t])
                os.close(fd)
            self._pre_enter_fd.clear()

            if cwd != os.getcwd():
                log.debug(f"cwd does in fact change after setns! {cwd} -> {os.getcwd()}")
            os.chdir(cwd)

        log.debug(f"{self}: __init__")

    def __repr__(self):
        nstargets = []
        for t, (target_type, target) in self._nstarget.items():
            if target_type == 'pid':
                nstargets.append(f'{t}@{self._fd[t]}=PID:{target}')
            elif target_type == 'path':
                nstargets.append(f'{t}@{self._fd[t]}=Path:{target}')
            elif target_type == 'anon':
                nstargets.append(f'{t}@{self._fd[t]}={target}')
        return f'<Namespace {",".join(nstargets)}>'

    def __del__(self):
        log.debug(f"{self}: __del__")

        for t, fd in self._pre_enter_fd.items():
            # return to original namespace
            log.debug(f"{self}: Restoring {t} namespace.")
            os.setns(fd, 0)     # nstype is 0 because we cannot be bothered to determine it at this stage.
            if t == 'mnt':
                os.chdir(self._mnt_cwd)

            # close namespace
            os.close(fd)

        for fd in self._fd.values():
            # close all namespace targets
            os.close(fd)

    def __getattr__(self, name):
        if name in Namespace.TYPES:
            return self._fd.get(name, None)

    def __enter__(self):
        for t, fd in self._fd.items():
            # save current namespace
            if t == 'mnt':
                self._mnt_cwd = os.getcwd()
            self._pre_enter_fd[t] = os.open(f'/proc/self/ns/{t}', 0)

            # enter new namespace
            log.debug(f"{self}: Entering {t} namespace.")
            try:
                os.unshare(Namespace.UNSHARE_FLAGS[t])    # HACK: i don't know why, but without this causes EINVAL
                os.setns(fd, Namespace.UNSHARE_FLAGS[t])

            except OSError:
                # revert
                for revert_t, revert_fd in self._pre_enter_fd.items():
                    if revert_t == t: continue
                    log.debug(f"{self}: Reverting {revert_t} namespace due to error.")
                    os.setns(revert_fd, 0)
                self._pre_enter_fd.clear()
                raise

        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        for t, fd in self._pre_enter_fd.items():
            # return to original namespace
            log.debug(f"{self}: Exiting {t} namespace.")
            os.setns(fd, Namespace.UNSHARE_FLAGS[t])
            if self._mnt_cwd:
                os.chdir(self._mnt_cwd)

            # close original fd
            os.close(fd)
        self._pre_enter_fd.clear()

    # def get_path(self, ns_type: str):
    #     if ns_type not in Namespace.TYPES:
    #         raise ValueError(f"Invalid namespace type '{ns_type}'")
    #     return f'/proc/{os.getpid()}/fd/{self._fd[ns_type]}'
    #     # TODO: check whether this path is correct when we are inside the namespace (pid namespace)


MS_RDONLY       = 1 << 0
MS_NOSUID       = 1 << 1
MS_NODEV        = 1 << 2
MS_NOEXEC       = 1 << 3
MS_SYNCHRONOUS  = 1 << 4
MS_REMOUNT      = 1 << 5
MS_MANDLOCK     = 1 << 6
MS_DIRSYNC      = 1 << 7
MS_NOSYMFOLLOW  = 1 << 8
MS_NOATIME      = 1 << 10
MS_NODIRATIME   = 1 << 11
MS_BIND         = 1 << 12
MS_MOVE         = 1 << 13
MS_REC          = 1 << 14
MS_SILENT       = 1 << 15
MS_POSIXACL     = 1 << 16
MS_UNBINDABLE   = 1 << 17
MS_PRIVATE      = 1 << 18
MS_SLAVE        = 1 << 19
MS_SHARED       = 1 << 20
MS_RELATIME     = 1 << 21
MS_KERNMOUNT    = 1 << 22
MS_I_VERSION    = 1 << 23
MS_STRICTATIME  = 1 << 24
MS_LAZYTIME     = 1 << 25

propagation_modes = {
    'shared': MS_SHARED,
    'slave': MS_SLAVE,
    'private': MS_PRIVATE,
    'unbindable': MS_UNBINDABLE
}

def mount(source: str, target: str, fs: str | None, options: Iterable[str] = None, remount=False, bind=False, propagation: str = None, move=False):
    # if not fs and bind is False:
    #     raise ValueError("fs can only be None if bind or remount is True")
    
    mountflags = 0
    if remount:
        mountflags |= MS_REMOUNT
    if bind:
        mountflags |= MS_BIND
    if move:
        mountflags |= MS_MOVE
    if isinstance(propagation, str):
        if propagation[0] == 'r':
            mountflags |= MS_REC
            propagation = propagation[1:]
        if propagation not in ('shared', 'slave', 'private', 'unbindable'):
            raise ValueError(f"Invalid propagation mode '{propagation}'")
        mountflags |= propagation_modes[propagation]

    src_val = source.encode() if source else None
    target_val = target.encode() if target else None
    fs_val = fs.encode() if fs else None
    opt_val = ','.join(options).encode() if options else None
    ret = libc.mount(src_val, target_val, fs_val, mountflags, opt_val)
    if ret != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))

def umount(target: str):
    ret = libc.umount(target.encode(), 0)
    if ret != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))
