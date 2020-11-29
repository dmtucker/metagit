"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""


import codecs
import glob
import os

import setuptools  # type: ignore


def read(*parts: str) -> str:
    """Read a file in this repository."""
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, *parts), "r") as file_:
        return file_.read()


if __name__ == "__main__":
    setuptools.setup(
        name="metagit",
        use_scm_version=True,
        url="https://github.com/dmtucker/metagit",
        description="A Git Project Manager",
        long_description=read("README.md"),
        long_description_content_type="text/markdown",
        author="David Tucker",
        author_email="david@tucker.name",
        license="LGPLv2+",
        package_dir={"": "src"},
        packages=setuptools.find_packages("src"),
        py_modules=[
            os.path.splitext(os.path.basename(path))[0]
            for path in glob.glob("src/*.py")
        ],
        include_package_data=True,
        setup_requires=["setuptools_scm >= 4.0"],
        python_requires=">= 3.6",
        install_requires=[
            "attrs >= 20.3",
            "click >= 7.1",
            "gitpython >= 3.1",
            "setuptools >= 49.6",
        ],
        entry_points={"console_scripts": ["metagit = metagit.__main__:main"]},
        classifiers=[
            "License :: OSI Approved :: "
            "GNU Lesser General Public License v2 or later (LGPLv2+)",
            "Intended Audience :: End Users/Desktop",
            "Programming Language :: Python :: 3.6",
            "Development Status :: 5 - Production/Stable",
        ],
    )
