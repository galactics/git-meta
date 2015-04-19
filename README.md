git-meta
========

Git meta is a small program enabling the power of system-wide status check of
all you git repositories.

![Terminal output](docs/source/_static/terminal.png)

It uses [pygit2](https://github.com/libgit2/pygit2), which is Python binding of
[libgit2](https://github.com/libgit2/libgit2), a standalone git library writen
in C.

Installation
------------

    # pip install git-meta

Alternatively, if you want to install `git-meta` from the sources:

    # python setup.py install

You can also install it in a [virtialenv](https://github.com/pypa/virtualenv) in
order to test and not mess your system configuration.

Documentation
-------------

The documentation uses [Sphinx](http://sphinx-doc.org/). To generate statics HTML
files, go to the `docs` folder and type

    $ make html

Unit testing
------------

In order to launch the tests sequence of the package, you need
[Pytest](http://pytest.org/latest/) and
[Pytest-cov](https://pypi.python.org/pypi/pytest-cov/) installed.

Just type

    $ py.test

at the root of the repository.

Old version of git-meta
-----------------------

The old version of git meta can be found [here](https://github.com/galactics/git-meta-old).

Todo
----

* At the moment, unit-tests aren't independents from one another.
