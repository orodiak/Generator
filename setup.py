from setuptools import setup, find_packages

setup(
    name="smy02-controller",
    version="0.1.0",
    description="Controller for Rhode Schwarz SMY02 signal generator",
    author="Your Name",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "pyvisa>=1.13.0",
        "pyvisa-py>=0.5.0",
        "PyQt5>=5.15.0",
        "matplotlib>=3.8.0",
        "numpy>=1.24.0",
        "pyserial>=3.5",
    ],
)
