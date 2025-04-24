from setuptools import setup

APP = ['keepalive.py']
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'KeepAlive.icns',  # Make sure this exists in your directory
    'packages': ['rumps'],
    'plist': {
        'CFBundleName': 'KeepAlive',
        'CFBundleShortVersionString': '1.1.0',
        'CFBundleVersion': '1.1.0',
        'CFBundleIdentifier': 'com.mumurlen.keepalive',
    },
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

