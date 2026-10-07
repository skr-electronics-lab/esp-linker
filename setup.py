#!/usr/bin/env python3
"""
ESP-Linker Python Library Setup
(c) 2025 SK Raihan / SKR Electronics Lab - All Rights Reserved.

Professional wireless GPIO control for ESP8266 boards with PyFirmata-inspired interface.
Complete IoT solution with firmware, Python library, CLI tools, and web dashboard.

Author: SK Raihan
Organization: SKR Electronics Lab
Website: https://www.skrelectronicslab.com
Email: skrelectronicslab@gmail.com
YouTube: https://www.youtube.com/@skr_electronics_lab
Instagram: https://www.instagram.com/skr_electronics_lab
GitHub: https://github.com/skr-electronics-lab
Support: https://buymeacoffee.com/skrelectronics
"""

from setuptools import setup, find_packages
import os
import sys

# Add the package directory to the path to import version
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'esp_linker'))
from version import __version__, AUTHOR, EMAIL, ORGANIZATION, WEBSITE, GITHUB, PYPI, YOUTUBE, INSTAGRAM, SUPPORT

# Read README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="esp-linker",
    version=__version__,
    author=AUTHOR,
    author_email=EMAIL,
    maintainer=ORGANIZATION,
    maintainer_email=EMAIL,
    description="Professional wireless GPIO and peripheral control for ESP8266 and ESP32 boards with PyFirmata-inspired interface, I2C hardware bus, OTA updates, CLI tools, and web dashboard",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=WEBSITE,
    download_url=PYPI,
    project_urls={
        "Homepage": WEBSITE,
        "Documentation": f"{WEBSITE}/esp-linker",
        "Source Code": GITHUB,
        "Bug Tracker": f"{GITHUB}/issues",
        "YouTube Channel": YOUTUBE,
        "Instagram": INSTAGRAM,
        "Support": SUPPORT,
        "PyPI": PYPI,
    },
    packages=find_packages(),
    package_data={
        'esp_linker': ['firmware/*.bin'],
    },
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Hardware",
        "Topic :: Home Automation",
        "Topic :: Scientific/Engineering",
        "Topic :: Education",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Communications",
        "Topic :: System :: Networking",
        "Topic :: Terminals :: Serial",
        "Topic :: Utilities",

        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3 :: Only",
        "Operating System :: OS Independent",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Natural Language :: English",
        "Framework :: Flask",
    ],
    python_requires=">=3.7",
    install_requires=requirements + [
        # Ensure zeroconf is explicitly included for auto-discovery
        "zeroconf>=0.38.0",
    ],
    extras_require={
        "dashboard": ["flask>=2.0.0"],
        "all": ["flask>=2.0.0", "zeroconf>=0.38.0"],
    },
    entry_points={
        "console_scripts": [
            "esp-linker=esp_linker.cli:main",
            "esp-linker-discover=esp_linker.cli:discover_devices_entry",
            "esp-linker-test=esp_linker.cli:test_device_entry",
            "esp-linker-flash=esp_linker.cli:flash_esp8266_entry",
            "esp-linker-ota=esp_linker.cli:ota_entry",
            "esp-linker-i2c=esp_linker.cli:i2c_entry",
            "esp-linker-events=esp_linker.cli:events_entry",
            "esp-linker-detect=esp_linker.cli:detect_esp8266_entry",
            "esp-linker-setup-wifi=esp_linker.cli:wifi_wizard_entry",
            "esp-linker-devices=esp_linker.cli:devices_entry",
            "esp-linker-dashboard=esp_linker.cli:dashboard_entry",
        ],
    },
    keywords=[
        "esp8266", "esp32", "gpio", "iot", "wireless", "arduino",
        "microcontroller", "automation", "robotics", "electronics",
        "maker", "diy", "wifi", "remote control", "firmware", "flash",
        "serial", "uart", "http", "rest", "api", "web", "dashboard",
        "sensor", "actuator", "pwm", "servo", "analog", "digital"
    ],
)