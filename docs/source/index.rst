.. git-meta documentation master file, created by
   sphinx-quickstart on Sat Dec 13 20:14:49 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

git-meta's documentation
========================

:Authors: Jules David <jules@onada.fr>
          Tristan Gregoire <tristan@onada.fr>
:Source code: `github.com project <https://github.com/galactis/gitmeta>`_
:Bug tracker: `github.com issues <https://github.com/galactics/gitmeta/issues>`_
:License: BSD
:Generated: |today|
:Version: |release|


git-meta allows you to get a clear picture of all your local repository states.

.. image:: /_static/terminal.png

It is based on the `gitpython <https://github.com/gitpython-developers/GitPython>`_ library

API
---

.. autoclass:: gitmeta.Meta
    :members:

.. autoclass:: gitmeta.Repo
    :members:
    :show-inheritance:


Tests
-----

git-meta tests are located in the test/ folder. They are powered by pytest.

In order to launch the test series, you only have to type the command :

.. code-block:: shell

    $ py.test

in the base folder.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

