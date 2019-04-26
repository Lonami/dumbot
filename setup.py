import os
import shutil
from distutils.core import setup

PKG_DIR = 'dumbot'
BOT_SRC = 'dumbot.py'
INIT_PY = os.path.join(PKG_DIR, '__init__.py')


try:
    if os.path.isfile(BOT_SRC):
        os.makedirs(PKG_DIR, exist_ok=True)
        shutil.copy(BOT_SRC, INIT_PY)

    setup(
        name='dumbot',
        packages=[PKG_DIR],
        version='1.4.2',
        description='dumb async telegram bot for python 3',
        author='Lonami Exo',
        author_email='totufals@hotmail.com',
        keywords='telegram async asyncio bot'.split(),
        classifiers=['Development Status :: 5 - Production/Stable',
                     'Framework :: AsyncIO',
                     'Intended Audience :: Developers',
                     'License :: OSI Approved :: MIT License',
                     'Programming Language :: Python :: 3',
                     'Topic :: Communications :: Chat'],
        install_requires=['aiohttp'],
    )
finally:
    if os.path.isfile(BOT_SRC):
        if os.path.isfile(INIT_PY):
            os.remove(INIT_PY)
        if os.path.isdir(PKG_DIR):
            os.rmdir(PKG_DIR)
