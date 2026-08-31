"""The wheel has to be PLATFORM-SPECIFIC but NOT tied to a Python version.

Inside it there is machine code - nashira3d.dll on Windows, libnashira3d.so on
Linux - so the tag py3-none-any would be a lie: such a wheel would install
anywhere and fall over at the first call.

But there is no C extension here: cffi works in ABI mode and reaches the
library through dlopen. So a cp312 tag is a lie as well, in the other
direction, and it costs nine extra wheels: one per Python version per
platform.

There is only one right tag: py3-none-<platform>. That is what is set below.
"""

from setuptools import setup
from setuptools.dist import Distribution

try:
    from setuptools.command.bdist_wheel import bdist_wheel
except ImportError:          # setuptools older than 70
    from wheel.bdist_wheel import bdist_wheel


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return True

    def is_pure(self):
        return False


class PlatformWheel(bdist_wheel):
    def finalize_options(self):
        bdist_wheel.finalize_options(self)
        self.root_is_pure = False

    def get_tag(self):
        _python, _abi, plat = bdist_wheel.get_tag(self)
        return "py3", "none", plat


setup(distclass=BinaryDistribution, cmdclass={"bdist_wheel": PlatformWheel})
