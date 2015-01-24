#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import pytest
import pygit2

import subprocess

from git.meta import Repo, Meta

working_dir = os.path.dirname(os.path.realpath(__file__))

repo_path = os.path.join(working_dir, "tmp-repository")
filepath = os.path.join(repo_path, 'dummy_file.txt')
ignored_path = os.path.join(repo_path, 'ignored.txt')
gitignore_path = os.path.join(repo_path, '.gitignore')

pygit2.init_repository(repo_path)
repo = Repo(repo_path)
author = pygit2.Signature("test_author", "author@example.com")
commiter = pygit2.Signature("test_commiter", "commiter@example.com")

cloned_repo = os.path.join(working_dir, 'cloned_repository')
dumb_repo = os.path.join(working_dir, 'dumb')

_clone = None
clone_filepath = os.path.join(cloned_repo, os.path.basename("pouet.txt"))

@pytest.fixture
def empty_repo():
    return repo


@pytest.fixture
def clean_repo():

    with open(filepath, 'w+') as new:
        new.write('hello, here is a test')

    repo.index.add(os.path.basename(filepath))
    repo.index.write()
    repo.create_commit('refs/heads/master',
                       author,
                       commiter,
                       "Initial commit",
                       repo.index.write_tree(),
                       [])

    return repo

@pytest.fixture
def dirty_repo():
    with open(filepath, 'w') as file_handler:
        file_handler.write("\nNew line")


@pytest.fixture
def dirty_index():
    repo.index.add(os.path.basename(filepath))
    repo.index.write()


@pytest.fixture
def clean_repo2():
    repo.create_commit('refs/heads/master',
                       author,
                       commiter,
                       "Second commit",
                       repo.index.write_tree(),
                       [repo.head.peel().id])


@pytest.fixture
def ignored_file():

    with open(gitignore_path, 'w+') as gitignore, open(ignored_path, 'w+') as ignored:
        gitignore.write(os.path.basename(ignored_path) + "\n")
        ignored.write("Whatever, this text won't be seen anyway")

    repo.index.add(os.path.basename(gitignore_path))
    repo.index.write()

    repo.create_commit('refs/heads/master',
                       author,
                       commiter,
                       "gitignore added",
                       repo.index.write_tree(),
                       [repo.head.peel().id])


@pytest.fixture
def clone():
    global _clone
    pygit2.clone_repository(repo_path, cloned_repo)
    _clone = Repo(cloned_repo)

    with open(filepath, 'w') as file_remote, open(clone_filepath, 'w') as file_clone:
        file_remote.write("\nThis is in the first repository")
        file_clone.write("\nThis is in the clone repository")

    repo.index.add_all()
    repo.index.write()
    repo.create_commit('refs/heads/master',
                       author,
                       commiter,
                       "New modification",
                       repo.index.write_tree(),
                       [repo.head.peel().id])

    with open(filepath, 'a') as file_remote:
        file_remote.write("\nNew line in the first repository")

    #repo.index.add_all()
    #repo.index.write()
    #repo.create_commit('refs/heads/master',
                       #author,
                       #commiter,
                       #"Second modification on the original repo",
                       #repo.index.write_tree(),
                       #[repo.head.peel().id])

    _clone.index.add_all()
    _clone.index.write()
    _clone.create_commit('refs/heads/master',
                       author,
                       commiter,
                       "New modification on the clone",
                       _clone.index.write_tree(),
                       [_clone.head.peel().id])

    with open(clone_filepath, 'a') as file_clone:
        file_clone.write("\nNew line in the second repository")

    _clone.index.add_all()
    _clone.index.write()
    _clone.create_commit('refs/heads/master',
                       author,
                       commiter,
                       "Second modification on the clone",
                       _clone.index.write_tree(),
                       [_clone.head.peel().id])

    _clone.remotes[0].fetch()

    return _clone


@pytest.fixture
def stashed():
    with open(filepath, 'w') as content:
        content.write("Modification\n")

    # I don't know how to do it the pygit2-way
    proc = subprocess.Popen(['git', 'stash'], cwd=repo_path)
    # wait until the end of the command
    proc.wait()


_meta = Meta()
_meta.config['scanroot'] = working_dir


@pytest.fixture
def mk_dumb_repo():
    os.makedirs(os.path.join(dumb_repo, '.git'))


@pytest.fixture
def pulling():
    remote_commit = _clone.lookup_branch('master').upstream.peel()
    _clone.merge(remote_commit.id)
    _clone.create_commit('refs/heads/master',
                         author,
                         commiter,
                         "Merge commit",
                         _clone.index.write_tree(),
                         [_clone.head.target, remote_commit.id])



def test_empty_repo(empty_repo):
    assert repo.status() == {}
    assert repo.is_empty == True


def test_clean_repo(clean_repo):
    assert repo.is_empty == False
    assert repo.status() == {}
    assert repo.statusline().endswith('[ \x1b[92mOK\x1b[39m ]') == True


def test_dirty_repo(dirty_repo):
    assert repo.status() == {os.path.basename(filepath): pygit2.GIT_STATUS_WT_MODIFIED}
    assert repo.statusline().endswith('[ \x1b[91mKO\x1b[39m ]') == True


def test_dirty_index(dirty_index):
    assert repo.status() == {os.path.basename(filepath): pygit2.GIT_STATUS_INDEX_MODIFIED}
    assert repo.statusline().endswith('[ \x1b[91mKO\x1b[39m ]') == True


def test_clean_repo2(clean_repo2):
    assert repo.status() == {}
    assert repo.statusline().endswith('[ \x1b[92mOK\x1b[39m ]') == True


def test_ignore(ignored_file):
    assert repo.status() == {}
    assert super(Repo, repo).status() == {os.path.basename(ignored_path): pygit2.GIT_STATUS_IGNORED}


def test_cloned(clone):
    assert _clone.remote_diff() == {'master': '2-1'}
    assert _clone.statusline().endswith('(master:2-1) [ \x1b[92mOK\x1b[39m ]') == True


def test_stashed(stashed):
    assert repo.stash() == True
    assert repo.statusline().endswith('(\x1b[93mstash\x1b[39m) [ \x1b[92mOK\x1b[39m ]') == True


def test_meta_discovery(mk_dumb_repo, capsys):
    _meta.discover()
    out, err = capsys.readouterr()
    assert out.startswith('Discovery of repositories')
    assert out.endswith('sub-directories\n')
    assert err == ""


def test_meta_scan(pulling, dirty_repo, capsys):

    _meta.scan()
    out, err = capsys.readouterr()
    lines = out.splitlines()
    assert lines[0].endswith('(master:1) [ \x1b[92mOK\x1b[39m ]')
    assert lines[1].endswith('(\x1b[93mstash\x1b[39m) [ \x1b[91mKO\x1b[39m ]')
    assert err == ""

    kwargs = {'filter_status': "OK"}
    _meta.scan(**kwargs)
    out, err = capsys.readouterr()
    assert out.endswith('(master:1) [ \x1b[92mOK\x1b[39m ]\n')

    kwargs = {'filter_status': "KO"}
    _meta.scan(**kwargs)
    out, err = capsys.readouterr()
    assert out.endswith('(\x1b[93mstash\x1b[39m) [ \x1b[91mKO\x1b[39m ]\n')


def test_clean_env():
    shutil.rmtree(repo_path)
    shutil.rmtree(cloned_repo)
    shutil.rmtree(dumb_repo)
    meta = Meta()
    meta.discover()
