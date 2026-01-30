from setuptools import setup, find_packages
setup(
    name="cortex-memory",
    packages=find_packages(),
    package_data={"cortex_memory": ["db/schema.sql"]},
)
