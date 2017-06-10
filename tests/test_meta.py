#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pytest
import pygit2

from git.meta import Repo, Meta

author = pygit2.Signature("test_author", "author@example.com")
commiter = pygit2.Signature("test_commiter", "commiter@example.com")

filename = "dummy_file.txt"
ignored_filename = "ignored_file.txt"


@pytest.yield_fixture
def empty_repo(tmpdir):

    repo_path = str(tmpdir.mkdir("repo.git"))

    pygit2.init_repository(repo_path)
    yield Repo(repo_path)


@pytest.fixture
def clean_repo(empty_repo):

    filepath = os.path.join(empty_repo.workdir, filename)

    with open(filepath, 'w+') as new:
        new.write('hello, here is a test')

    empty_repo.index.add(os.path.basename(filepath))
    empty_repo.index.write()
    empty_repo.create_commit(
        'refs/heads/master',
        author,
        commiter,
        "Initial commit",
        empty_repo.index.write_tree(),
        [])

    return empty_repo


@pytest.fixture
def dirty_repo(clean_repo):

    filepath = os.path.join(clean_repo.workdir, filename)

    with open(filepath, 'w') as file_handler:
        file_handler.write("\nNew line")

    return clean_repo


@pytest.fixture
def dirty_index(dirty_repo):
    filepath = os.path.join(dirty_repo.workdir, filename)

    dirty_repo.index.add(os.path.basename(filepath))
    dirty_repo.index.write()

    return dirty_repo


@pytest.fixture
def clean_repo2(dirty_index):
    dirty_index.create_commit(
        'refs/heads/master',
        author,
        commiter,
        "Second commit",
        dirty_index.index.write_tree(),
        [dirty_index.head.peel().id]
    )

    return dirty_index


@pytest.fixture
def ignored_file(clean_repo2):

    gitignore_path = os.path.join(clean_repo2.workdir, ".gitignore")
    ignored_path = os.path.join(clean_repo2.workdir, ignored_filename)

    with open(gitignore_path, 'w+') as gitignore, open(ignored_path, 'w+') as ignored:
        gitignore.write(os.path.basename(ignored_path) + "\n")
        ignored.write("Whatever, this text won't be seen anyway")

    clean_repo2.index.add(os.path.basename(gitignore_path))
    clean_repo2.index.write()

    clean_repo2.create_commit(
        'refs/heads/master',
        author,
        commiter,
        "gitignore added",
        clean_repo2.index.write_tree(),
        [clean_repo2.head.peel().id])

    return clean_repo2


@pytest.fixture
def clone(tmpdir, clean_repo2):

    cloned_repo_path = str(tmpdir.mkdir("clone.git"))

    pygit2.clone_repository(clean_repo2.workdir, cloned_repo_path)
    clone_repo = Repo(cloned_repo_path)

    filepath = os.path.join(clean_repo2.workdir, filename)
    clone_filepath = os.path.join(clone_repo.workdir, filename)

    # Modification of same file on both original and cloned repositories
    with open(filepath, 'a') as file_original, open(clone_filepath, 'a') as file_cloned:
        file_original.write("\nThis is in the first repository")
        file_cloned.write("\nThis is in the clone repository")

    # Create commit from modifications on original repository
    clean_repo2.index.add_all()
    clean_repo2.index.write()
    clean_repo2.create_commit(
        'refs/heads/master',
        author,
        commiter,
        "New modification",
        clean_repo2.index.write_tree(),
        [clean_repo2.head.peel().id])

    # New uncommited changes to the original repository
    with open(filepath, 'a') as file_original:
        file_original.write("\nNew line in the first repository")

    # Commit of the first
    clone_repo.index.add_all()
    clone_repo.index.write()
    clone_repo.create_commit(
        'refs/heads/master',
        author,
        commiter,
        "New modification on the clone",
        clone_repo.index.write_tree(),
        [clone_repo.head.peel().id])

    # Second modification on the cloned repository
    with open(clone_filepath, 'a') as file_cloned:
        file_cloned.write("\nNew line in the second repository")

    clone_repo.index.add_all()
    clone_repo.index.write()
    clone_repo.create_commit(
        'refs/heads/master',
        author,
        commiter,
        "Second modification on the clone",
        clone_repo.index.write_tree(),
        [clone_repo.head.peel().id])

    clone_repo.remotes[0].fetch()

    return (clean_repo2, clone_repo)


@pytest.fixture
def stashed(clean_repo2):
    filepath = os.path.join(clean_repo2.workdir, filename)

    with open(filepath, 'w') as content:
        content.write("Modification\n")

    clean_repo2.stash(author, "WIP: stashing")

    return clean_repo2


@pytest.fixture
def mk_dumb_repo(tmpdir):
    return str(tmpdir.makedirs("dumbrepos/.git/"))


@pytest.fixture
def pulling(clone):
    # We go back two commits, in order to have a clean merge
    # i.e. we decide that the original repository has a better
    # modification
    original, clone = clone
    clone.reset(clone.head.peel().parents[0].parents[0].oid, pygit2.GIT_RESET_HARD)

    remote_commit = clone.lookup_branch('master').upstream.peel()
    clone.merge(remote_commit.id)
    clone.create_commit(
        'refs/heads/master',
        author,
        commiter,
        "Merge commit",
        clone.index.write_tree(),
        [clone.head.target, remote_commit.id])

    return clone


@pytest.yield_fixture
def meta(tmpdir, pulling):
    meta = Meta()
    old = meta.config['scanroot']
    meta.config['scanroot'] = str(tmpdir)
    yield meta
    meta.config['scanroot'] = old
    meta.discover()


def test_empty_repo(empty_repo):
    assert empty_repo.status() == {}
    assert empty_repo.is_empty is True


def test_clean_repo(clean_repo):
    assert clean_repo.is_empty is False
    assert clean_repo.status() == {}
    assert clean_repo.statusline().endswith('[ \x1b[92mOK\x1b[39m ]') is True


def test_dirty_repo(dirty_repo):
    assert dirty_repo.status() == {filename: pygit2.GIT_STATUS_WT_MODIFIED}
    assert dirty_repo.statusline().endswith('[ \x1b[91mKO\x1b[39m ]') is True


def test_dirty_index(dirty_index):
    assert dirty_index.status() == {filename: pygit2.GIT_STATUS_INDEX_MODIFIED}
    assert dirty_index.statusline().endswith('[ \x1b[91mKO\x1b[39m ]') is True


def test_clean_repo2(clean_repo2):
    assert clean_repo2.status() == {}
    assert clean_repo2.statusline().endswith('[ \x1b[92mOK\x1b[39m ]') is True


def test_ignore(ignored_file):
    assert ignored_file.status() == {}
    assert super(Repo, ignored_file).status() == {ignored_filename: pygit2.GIT_STATUS_IGNORED}


def test_cloned(clone):
    original, clone = clone
    assert original.remote_diff() == {}
    assert clone.remote_diff() == {'master': '2-1'}
    assert clone.statusline().endswith('(master:2-1) [ \x1b[92mOK\x1b[39m ]') is True


def test_stashed(stashed):
    assert stashed.stashed() is True
    assert stashed.statusline().endswith('(\x1b[93mstash\x1b[39m) [ \x1b[92mOK\x1b[39m ]') is True


@pytest.mark.skip
def test_meta_discovery(meta, capsys):
    meta.discover()
    out, err = capsys.readouterr()
    assert out.startswith('Discovery of repositories')
    assert out.endswith('sub-directories\n')
    assert err == ""


@pytest.mark.skip
def test_meta_scan(meta, dirty_repo, capsys):

    meta.discover()
    # Purge of capsys, as discover is not the tested method here
    out, err = capsys.readouterr()

    meta.scan()
    out, err = capsys.readouterr()
    lines = out.splitlines()
    assert lines[0].endswith('(master:1) [ \x1b[92mOK\x1b[39m ]')
    assert lines[1].endswith(' \x1b[91mKO\x1b[39m ]')
    assert err == ""

    meta.scan(filter_status="OK")
    out, err = capsys.readouterr()
    assert out.endswith('(master:1) [ \x1b[92mOK\x1b[39m ]\n')

    meta.scan(filter_status="KO")
    out, err = capsys.readouterr()
    assert out.endswith('[ \x1b[91mKO\x1b[39m ]\n')

    meta.scan(filter_status="rdiff")
    out, err = capsys.readouterr()
    assert out.endswith('(master:1) [ \x1b[92mOK\x1b[39m ]\n')
