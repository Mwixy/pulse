# setup.py in C:\Users\Ege\Pulse
from setuptools import setup, find_packages

setup(
    name="pulse",
    version="0.1",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'pulse=pulse.cli:main',
        ],
    },
)