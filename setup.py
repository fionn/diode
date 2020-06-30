"""setup"""
import setuptools # type: ignore
from pip._internal.req import parse_requirements # type: ignore

from diode import name, __version__

with open("README.md", "r") as fh:
    # pylint: disable=invalid-name
    long_description = fh.read()

# pylint: disable=invalid-name
requirements = parse_requirements("requirements.txt", session="setup")

setuptools.setup(
    name=name,
    version=__version__,
    author="FF",
    description="Send and receive data over serial diode",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/fionn/diode",
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
    install_requires=[str(req.req) for req in requirements],
    extras_require={"dev": ["pylint", "mypy"]},
    data_files=[("bash_completion", ["bash_completion/diode"])],
    entry_points={"console_scripts": ["diode = diode.main:main"]},
    platforms=["Unix"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 3 - Alpha",
        "Operating System :: Unix",
    ],
)
