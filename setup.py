# -*- coding: utf-8 -*-

from setuptools import setup, find_packages, Command

install_requires = ['pygit2==0.22.0']
version = "0.1.2"

class PyTest(Command):
    user_options = []
    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import sys,subprocess
        errno = subprocess.call(['py.test'])
        raise SystemExit(errno)

class Doc(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import os, subprocess
        errno = subprocess.call(['make', '-C', 'docs/', 'html'])
        raise SystemExit(errno)

setup(
    name='git-meta',
    version=version,
    description="Git reposiroties manager",
    platforms=["any"],
    keywords='git',
    author='Jules David',
    author_email='jules@onada.fr',
    url='https://github.com/galactics/git-meta',
    license='BSD',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    namespace_packages=['git'],
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "git-meta = git.meta:main"
        ]
    },
    cmdclass = {
        'test': PyTest,
        'docs': Doc,
    },
    extras_require={
        'test': [
            'flake8',
            'pytest',
            'pytest-cov',
        ],
        'develop': [
            'Sphinx',
            'sphinxcontrib-napoleon'
        ],
    }
)
