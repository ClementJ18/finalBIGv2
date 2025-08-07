from setuptools import setup, find_packages
import re

version = ""
with open("pyBIG/__init__.py") as f:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE).group(1)

if not version:
    raise RuntimeError("version is not set")

readme = ""
with open("README.md") as f:
    readme = f.read()

setup(
    name="pyBIG",
    version=version,
    url="https://github.com/ClementJ18/pyBIG",
    packages=find_packages(include=["pyBIG", "pyBIG.*"]),
    description="A library for manipulating BIG format archives",
    long_description_content_type="text/markdown",
    long_description=readme,
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
)
