# -*- coding: utf-8 -*-

from setuptools import setup, find_packages, Command

install_requires = ['pygit2==0.22.0']
version = "0.1.2"



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
