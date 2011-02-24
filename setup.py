#!/usr/bin/env python

# Based off http://chrismiles.livejournal.com/23399.html

import sys

try:
    import twisted
except ImportError:
    raise SystemExit("Twisted not found. Make sure you "
                     "have installed the Twisted core package.")

from distutils.core import setup


def refresh_plugin_cache():
    from twisted.plugin import IPlugin, getPlugins
    list(getPlugins(IPlugin))

if __name__ == "__main__":
    setup(name='curler',
          version='1.0',
          description='Gearman worker that hits a web service to do work.',
          author='Garret Heaton',
          author_email='powdahound@gmail.com',
          url='http://github.com/powdahound/curler',
          packages=['curler',
                    'curler.twisted_gears',
                    'twisted.plugins'],
          package_data={
              'twisted': ['plugins/curler_plugin.py']}
          )

    refresh_plugin_cache()
