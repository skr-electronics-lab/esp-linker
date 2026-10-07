"""
ESP-Linker Version Management
(c) 2025 SK Raihan / SKR Electronics Lab -- All Rights Reserved.

Single source of truth for version numbers across firmware and library
"""

# Version information - SINGLE SOURCE OF TRUTH
__version__ = "1.4.2"
__firmware_version__ = "1.4.2"

# Version components
VERSION_MAJOR = 1
VERSION_MINOR = 4
VERSION_PATCH = 2

# Build version tuple
VERSION_TUPLE = (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH)

# Version string for display
VERSION_STRING = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"

# Firmware name
FIRMWARE_NAME = "ESP-Linker"

# Library metadata
LIBRARY_NAME = "esp-linker"
AUTHOR = "SK Raihan"
EMAIL = "skrelectronicslab@gmail.com"
ORGANIZATION = "SKR Electronics Lab"
LICENSE = "MIT"
COPYRIGHT = "(c) 2025 SK Raihan / SKR Electronics Lab"

# URLs and links
WEBSITE = "https://www.skrelectronicslab.com"
GITHUB = "https://github.com/skr-electronics-lab/esp-linker"
PYPI = "https://pypi.org/project/esp-linker/"
YOUTUBE = "https://www.youtube.com/@skr_electronics_lab"
INSTAGRAM = "https://www.instagram.com/skr_electronics_lab"
SUPPORT = "https://buymeacoffee.com/skrelectronics"

def get_version():
    """Get the current version string"""
    return __version__

def get_firmware_version():
    """Get the current firmware version string"""
    return __firmware_version__

def get_version_info():
    """Get detailed version information"""
    return {
        'version': __version__,
        'firmware_version': __firmware_version__,
        'version_tuple': VERSION_TUPLE,
        'library_name': LIBRARY_NAME,
        'firmware_name': FIRMWARE_NAME,
        'author': AUTHOR,
        'organization': ORGANIZATION,
        'license': LICENSE,
        'copyright': COPYRIGHT,
        'website': WEBSITE,
        'github': GITHUB,
        'pypi': PYPI
    }

def print_version_info():
    """Print version information"""
    info = get_version_info()
    print(f"{info['library_name']} v{info['version']}")
    print(f"Firmware: {info['firmware_name']} v{info['firmware_version']}")
    print(f"Author: {info['author']} ({info['organization']})")
    print(f"License: {info['license']}")
    print(f"Website: {info['website']}")
