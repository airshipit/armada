import setuptools

try:
    import multiprocessing  # noqa
except ImportError:
    pass

setuptools.setup(package_data={'armada': ['schemas/*.yaml']},
                 include_package_data=True,
                 setup_requires=['pbr>=2.0.0'],
                 pbr=True)
