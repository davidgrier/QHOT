from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version('QHOT')
except PackageNotFoundError:  # package not installed (e.g. bare source checkout)
    __version__ = 'unknown'
