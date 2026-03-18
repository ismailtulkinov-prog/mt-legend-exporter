# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import py_compile
import shutil
import sys
import zipfile

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SOURCE_FILE = os.path.join(
    ROOT_DIR, 'source', 'scripts', 'client', 'gui', 'mods', 'mod_mt_legend_exporter.py'
)
META_FILE = os.path.join(ROOT_DIR, 'res', 'meta', 'MTLegendExporter.xml')
CONFIG_TEMPLATE = os.path.join(ROOT_DIR, 'configs', 'mt_legend_exporter', 'config.example.json')
BUILD_DIR = os.path.join(ROOT_DIR, 'build')
DIST_DIR = os.path.join(ROOT_DIR, 'dist')
INSTALL_DIR = os.path.join(DIST_DIR, 'install', 'mods')
CONFIG_INSTALL_DIR = os.path.join(INSTALL_DIR, 'configs', 'mt_legend_exporter')
PYC_FILE = os.path.join(BUILD_DIR, 'res', 'scripts', 'client', 'gui', 'mods', 'mod_mt_legend_exporter.pyc')
MTMOD_FILE = os.path.join(INSTALL_DIR, 'mod_mt_legend_exporter.mtmod')
INSTALL_ZIP_FILE = os.path.join(DIST_DIR, 'mt_legend_exporter_install.zip')


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def main():
    if sys.version_info[:2] != (2, 7):
        print('This build script must be started with Python 2.7.')
        print('Example on Windows: py -2 tools\\build_mtmod.py')
        return 1

    if os.path.isdir(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    if os.path.isdir(DIST_DIR):
        shutil.rmtree(DIST_DIR)

    ensure_dir(os.path.dirname(PYC_FILE))
    ensure_dir(CONFIG_INSTALL_DIR)

    py_compile.compile(SOURCE_FILE, cfile=PYC_FILE, doraise=True)

    with zipfile.ZipFile(MTMOD_FILE, 'w', zipfile.ZIP_STORED) as archive:
        archive.write(META_FILE, 'meta.xml')
        archive.write(PYC_FILE, 'res/scripts/client/gui/mods/mod_mt_legend_exporter.pyc')

    shutil.copyfile(CONFIG_TEMPLATE, os.path.join(CONFIG_INSTALL_DIR, 'config.json'))
    with zipfile.ZipFile(INSTALL_ZIP_FILE, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(MTMOD_FILE, 'mods/mod_mt_legend_exporter.mtmod')
        archive.write(
            os.path.join(CONFIG_INSTALL_DIR, 'config.json'),
            'mods/configs/mt_legend_exporter/config.json'
        )

    print('Done.')
    print('Archive : {0}'.format(MTMOD_FILE))
    print('Config  : {0}'.format(os.path.join(CONFIG_INSTALL_DIR, 'config.json')))
    print('Install : {0}'.format(INSTALL_ZIP_FILE))
    return 0


if __name__ == '__main__':
    sys.exit(main())
