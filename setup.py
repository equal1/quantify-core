#!/usr/bin/env python
# pylint: disable=import-outside-toplevel
from setuptools import setup
from sys import stderr
import platform

def get_version_and_cmdclass(pkg_path):
    """Load version.py module without importing the whole package.

    Template code from miniver
    """
    import os
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("version", os.path.join(pkg_path, "_version.py"))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.__version__, module.get_cmdclass(pkg_path)


version, cmdclass = get_version_and_cmdclass(r"quantify_core")


qt5_blacklist = [
    ('Linux', 'aarch64'),
    ('Darwin', 'arm64')
]

if (platform.system(), platform.machine()) not in qt5_blacklist:
    with open("requirements_qt5.txt") as qt_requirements_file:
        requirements.extend(qt_requirements_file.read().splitlines())
else:
    print(f"WARNING: Qt and PyQtGraph will need to be installed manually for {platform.system()} / {platform.machine()}", file=stderr)
setup(
    version=version,
    cmdclass=cmdclass,
)
