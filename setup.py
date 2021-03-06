#!/usr/bin/env python

from __future__ import with_statement, print_function

import os
import sys
from distutils.version import LooseVersion
from setuptools import setup, Command
import setuptools.command.build_py
from buildutils.zmq.configure import Configure as ConfigureZmq
from buildutils.czmq.configure import Configure as ConfigureCzmq
from buildutils.zyre.configure import Configure as ConfigureZyre
from ctypes import *
from buildutils.czmq.msg import fatal
from subprocess import Popen, PIPE
from setuptools.dist import Distribution
from pprint import pprint

import versioneer

# vagrant doesn't appreciate hard-linking
if os.environ.get('USER') == 'vagrant' or os.path.isdir('/vagrant'):
    del os.link

# https://www.pydanny.com/python-dot-py-tricks.html
if sys.argv[-1] == 'test':
    test_requirements = [
        'pytest',
    ]
    try:
        modules = map(__import__, test_requirements)
    except ImportError as e:
        err_msg = e.message.replace("No module named ", "")
        msg = "%s is not installed. Install your test requirements." % err_msg
        raise ImportError(msg)
    r = os.system('py.test test -v')
    if r == 0:
        sys.exit()
    else:
        raise RuntimeError('tests failed')

try:
    import Cython
    if LooseVersion(Cython.__version__) < LooseVersion('0.16'):
        raise ImportError("Cython >= 0.16 required, found %s" % Cython.__version__)
    try:
        # Cython 0.25 or later
        from Cython.Distutils.old_build_ext import old_build_ext as build_ext_c
    except ImportError:
        from Cython.Distutils import build_ext as build_ext_c
except Exception as e:
    raise ImportError('Cython >= 0.16 required')


libuuid = 'libuuid.so'
if sys.platform == 'darwin':
    libuuid = '/opt/local/lib/libuuid.dylib'

if sys.platform.startswith('win'):
    libuuid = None

if libuuid:
    try:
        cdll.LoadLibrary(libuuid)
    except OSError:
        raise ImportError('Requires uuid-dev and libuuid1 to be installed')

pypy = 'PyPy' in sys.version


# set dylib ext:
if sys.platform.startswith('win'):
    lib_ext = '.dll'
else:
    lib_ext = '.so'

for idx, arg in enumerate(list(sys.argv)):
    if arg == 'egg_info':
        sys.argv.pop(idx)
        sys.argv.insert(idx, 'build')
        sys.argv.insert(idx+1, 'egg_info')


class zbuild_ext(build_ext_c):

    def finalize_options(self):
        build_ext_c.finalize_options(self)
        # set binding so that compiled methods can be inspected
        self.cython_directives['binding'] = True

    def build_extensions(self):
        # if self.compiler.compiler_type == 'mingw32':
        #     customize_mingw(self.compiler)
        return build_ext_c.build_extensions(self)

    def build_extension(self, ext):
        build_ext_c.build_extension(self, ext)

    def run(self):

        self.distribution.run_command('configure_zmq')
        self.distribution.run_command('configure_czmq')
        self.distribution.run_command('configure')

        r = build_ext_c.run(self)

        if sys.platform != 'darwin':
            return r

        cmds = []
        cmds.append(
            ['install_name_tool', '-change', 'build/lib/czmq/libzmq.so', 'czmq/libzmq.so',
             'build/lib/czmq/libczmq.so']
        )
        cmds.append(
            ['install_name_tool', '-change', 'build/lib/czmq/libzmq.so', 'czmq/libzmq.so',
             'build/lib/zyre/libzyre.so']
        )

        cmds.append(
            ['install_name_tool', '-change', 'build/lib/czmq/libczmq.so', 'czmq/libczmq.so',
             'build/lib/zyre/libzyre.so']
        )

        for c in cmds:
            try:
                p = Popen(c, stdout=PIPE, stderr=PIPE)

            except OSError:
                fatal("install_name_tool not found, cannot patch libzmq for bundling.")

            out, err = p.communicate()
            if p.returncode:
                fatal("Could not patch bundled libzmq install_name: %s" % err, p.returncode)

        return r


class BinaryDistribution(Distribution):
    """Distribution which always forces a binary package with platform name"""
    def has_ext_modules(foo):
        if sys.platform == 'darwin':
            return True

class BuildPyCommand(setuptools.command.build_py.build_py):
  """Custom build command."""

  def run(self):
    self.run_command('build_ext')
    setuptools.command.build_py.build_py.run(self)

cmdclass = versioneer.get_cmdclass()
cmdclass = {
    'configure': ConfigureZyre,
    'configure_zmq': ConfigureZmq,
    'configure_czmq': ConfigureCzmq,
    'build_ext': zbuild_ext,
    'build_py': BuildPyCommand,
}

packages = ['czmq', 'zyre', 'pyzyre']

package_data = {
    'zyre': ['*' + lib_ext]
}

extensions = []


setup(
    name="pyzyre",
    version=versioneer.get_version(),
    packages=packages,
    ext_modules=extensions,
    package_data=package_data,
    author="Wes Young",
    author_email="wes@barely3am.com",
    url='https://github.com/wesyoung/pyzyre',
    description="",
    long_description="",
    license="MPL2",
    cmdclass=cmdclass,
    distclass=BinaryDistribution,
    install_requires=[
        'netifaces',
        'netaddr',
        'cython>=0.16',
        'names',
        'pyzmq',
        'tornado',
        'pyzmq>=16.0.1'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)'
    ],
    entry_points={
        'console_scripts': [
            'zyre-chat=pyzyre.client:main',
            'zyre-proxy=pyzyre.proxy:main',
            'zyre-gateway=pyzyre.gateway:main'
        ]
    }
)

