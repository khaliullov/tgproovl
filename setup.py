# -*- coding: utf-8 -*-

import os
import re
from setuptools import setup, find_packages
from distutils.util import convert_path


ROOT = os.path.dirname(__file__)
VERSION_RE = re.compile(r'''__version__ = ['"]([0-9]+\.[0-9]+\.[0-9]+)['"]''')


def get_version():
    init = open(os.path.join(ROOT, 'tgproovl', '__init__.py')).read()
    return VERSION_RE.search(init).group(1)


setup(
    name='tgproovl',
    version=get_version(),
    packages=find_packages(exclude=['tests*']),
    entry_points={
        'console_scripts': [
            'tgproovl = tgproovl.app:main'
        ]
    },
    description='Telegram bot for proovl',
    long_description=open(convert_path('README.md')).read(),
    url='https://github.com/khaliullov/tgproovl',
    author='Leandr Khaliullov',
    author_email='leandr@cpan.org',
    classifiers=[
        'Development Status :: 3 - Alpha Development Status',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Proprietary License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
