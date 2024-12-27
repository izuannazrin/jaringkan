from enum import IntEnum
from typing import Iterable
import os
import ctypes, ctypes.util


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

    _outside_wd: str | None
    _inside_wd: str | None

    def __init__(self, **kwargs):
        self._nstarget = {}
        self._fd = {}
        self._pre_enter_fd = {}
        self._outside_wd = None
        self._inside_wd = None

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

            if 'mnt' in anon_ns:
                # anonymount mnt namespace have my special ability to stay in the same cwd
                self._outside_wd = os.getcwd()
                self._inside_wd = os.getcwd()

            os.unshare(sum(Namespace.UNSHARE_FLAGS[t] for t in anon_ns))
            for t in anon_ns:
                self._fd[t] = os.open(f'/proc/self/ns/{t}', 0)
                self._nstarget[t] = ('anon', os.readlink(f'/proc/self/ns/{t}'))

            # restore namespace
            for t, fd in self._pre_enter_fd.items():
                os.setns(fd, Namespace.UNSHARE_FLAGS[t])
                os.close(fd)
            self._pre_enter_fd.clear()
            
            if 'mnt' in anon_ns:
                os.chdir(self._outside_wd)

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
        for t, fd in self._pre_enter_fd.items():
            # return to original namespace
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
            self._pre_enter_fd[t] = os.open(f'/proc/self/ns/{t}', 0)

            if t == 'mnt':
                self._outside_wd = os.getcwd()

            # enter new namespace
            try:
                os.unshare(Namespace.UNSHARE_FLAGS[t])    # HACK: i don't know why, but without this causes EINVAL
                os.setns(fd, Namespace.UNSHARE_FLAGS[t])

                if t == 'mnt' and self._inside_wd:
                    os.chdir(self._inside_wd)

            except OSError:
                # revert
                for revert_t, revert_fd in self._pre_enter_fd.items():
                    if revert_t == t: continue
                    os.setns(revert_fd, 0)
                    if revert_t == 'mnt':
                        os.chdir(self._outside_wd)
                self._pre_enter_fd.clear()
                raise

        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        for t, fd in self._pre_enter_fd.items():
            if t == 'mnt':
                self._inside_wd = os.getcwd()

            # return to original namespace
            os.setns(fd, Namespace.UNSHARE_FLAGS[t])

            if t == 'mnt':
                os.chdir(self._outside_wd)

            # close original fd
            os.close(fd)
        self._pre_enter_fd.clear()


class MountOptions(IntEnum):
    RDONLY      = 1 << 0
    NOSUID      = 1 << 1
    NODEV       = 1 << 2
    NOEXEC      = 1 << 3
    SYNCHRONOUS = 1 << 4
    REMOUNT     = 1 << 5
    MANDLOCK    = 1 << 6
    DIRSYNC     = 1 << 7
    NOSYMFOLLOW = 1 << 8
    NOATIME     = 1 << 10
    NODIRATIME  = 1 << 11
    BIND        = 1 << 12
    MOVE        = 1 << 13
    REC         = 1 << 14   # recursive
    SILENT      = 1 << 15
    POSIXACL    = 1 << 16
    UNBINDABLE  = 1 << 17
    PRIVATE     = 1 << 18
    SLAVE       = 1 << 19
    SHARED      = 1 << 20
    RELATIME    = 1 << 21
    KERNMOUNT   = 1 << 22
    I_VERSION   = 1 << 23
    STRICTATIME = 1 << 24
    LAZYTIME    = 1 << 25


class MountPropagationMode(IntEnum):
    SHARED      = MountOptions.SHARED
    SLAVE       = MountOptions.SLAVE
    PRIVATE     = MountOptions.PRIVATE
    UNBINDABLE  = MountOptions.UNBINDABLE


def mount(source: str, target: str, fs: str | None, options: Iterable[MountOptions | str] = None, remount=False, bind=False, propagation: MountPropagationMode | str = None, move=False):
    mountflags = 0
    if remount:
        mountflags |= MountOptions.REMOUNT
    if bind:
        mountflags |= MountOptions.BIND
    if move:
        mountflags |= MountOptions.MOVE
    if options:
        for opt in options:
            if isinstance(opt, (MountOptions, int)):
                mountflags |= opt
            elif isinstance(opt, str):
                try:
                    mountflags |= MountOptions[opt.upper()]
                except KeyError:
                    raise ValueError(f"Invalid mount option '{opt}'")
            else:
                raise TypeError(f"Expected MountOptions or str, got {type(opt)}")

    if isinstance(propagation, MountPropagationMode):
        mountflags |= propagation
    elif isinstance(propagation, str):
        if propagation[0] == 'r':
            mountflags |= MountOptions.REC
            propagation = propagation[1:]
        try:
            mountflags |= MountPropagationMode[propagation.upper()]
        except KeyError:
            raise ValueError(f"Invalid propagation mode '{propagation}'")

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
