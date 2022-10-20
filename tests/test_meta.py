#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import git
from pytest import fixture, mark

from gitmeta import Repo, Meta

author = git.Actor("test_author", "author@example.com")
committer = git.Actor("test_committer", "committer@example.com")

filename = "dummy_file.txt"
ignored_filename = "ignored_file.txt"


@fixture
def empty_repo(tmpdir):

    repo_path = str(tmpdir.mkdir("repo.git"))
    Repo.init(repo_path)
    yield Repo(repo_path)


@fixture
def clean_repo(empty_repo):

    filepath = os.path.join(empty_repo.working_dir, filename)

    with open(filepath, "w+") as new:
        new.write("hello, here is a test")

    empty_repo.index.add(filepath)
    empty_repo.index.write()
    empty_repo.index.commit("Initial commit", author=author, committer=committer)
    return empty_repo


@fixture
def dirty_repo(clean_repo):

    filepath = os.path.join(clean_repo.working_dir, filename)

    with open(filepath, "w") as file_handler:
        file_handler.write("\nNew line")

    return clean_repo


@fixture
def dirty_index(dirty_repo):
    filepath = os.path.join(dirty_repo.working_dir, filename)

    dirty_repo.index.add(os.path.basename(filepath))
    dirty_repo.index.write()

    return dirty_repo


@fixture
def clean_repo2(dirty_index):
    dirty_index.index.commit("Second commit", author=author, committer=committer)

    return dirty_index


@fixture
def ignored_file(clean_repo2):

    gitignore_path = os.path.join(clean_repo2.working_dir, ".gitignore")
    ignored_path = os.path.join(clean_repo2.working_dir, ignored_filename)

    with open(gitignore_path, "w+") as gitignore, open(ignored_path, "w+") as ignored:
        gitignore.write(os.path.basename(ignored_path) + "\n")
        ignored.write("Whatever, this text won't be seen anyway")

    clean_repo2.index.add(os.path.basename(gitignore_path))
    clean_repo2.index.write()

    clean_repo2.index.commit("gitignore added", author=author, committer=committer)

    return clean_repo2


@fixture
def clone(tmpdir, clean_repo2):

    cloned_repo_path = str(tmpdir.mkdir("clone.git"))

    clone_repo = clean_repo2.clone(cloned_repo_path)

    filepath = os.path.join(clean_repo2.working_dir, filename)
    clone_filepath = os.path.join(clone_repo.working_dir, filename)

    # Modification of same file on both original and cloned repositories
    with open(filepath, "a") as file_original, open(clone_filepath, "a") as file_cloned:
        file_original.write("\nThis is in the first repository")
        file_cloned.write("\nThis is in the clone repository")

    # Create commit from modifications on original repository
    clean_repo2.index.add(filepath)
    clean_repo2.index.write()
    clean_repo2.index.commit("New modification", author=author, committer=committer)

    # New uncommited changes to the original repository
    with open(filepath, "a") as file_original:
        file_original.write("\nNew line in the first repository")

    # Commit of the first
    clone_repo.index.add(clone_filepath)
    clone_repo.index.write()
    clone_repo.index.commit(
        "New modification on the clone", author=author, committer=committer
    )

    # Second modification on the cloned repository
    with open(clone_filepath, "a") as file_cloned:
        file_cloned.write("\nNew line in the second repository")

    clone_repo.index.add(clone_filepath)
    clone_repo.index.write()
    clone_repo.index.commit(
        "Second modification on the clone", author=author, committer=committer
    )

    clone_repo.remotes[0].fetch()

    return (clean_repo2, clone_repo)


@fixture
def stashed(clean_repo2):
    filepath = os.path.join(clean_repo2.working_dir, filename)

    with open(filepath, "w") as content:
        content.write("Modification\n")

    clean_repo2.git.stash("save")

    return clean_repo2


@fixture
def mk_dumb_repo(tmpdir):
    return str(tmpdir.makedirs("dumbrepos/.git/"))


@fixture
def pulling(clone):
    # We go back two commits, in order to have a clean merge
    # i.e. we decide that the original repository has a better
    # modification
    original, clone = clone
    clone.active_branch.set_commit("HEAD~2")

    remote_commit = clone.active_branch.tracking_branch().commit
    clone.index.merge_tree(remote_commit)
    clone.index.commit("Merge commit", author=author, committer=committer)

    return clone


@fixture
def meta(tmpdir, pulling):
    meta = Meta()
    old = meta.config["scanroot"]
    meta.config["scanroot"] = str(tmpdir)
    yield meta
    meta.config["scanroot"] = old
    meta.discover()


def test_empty_repo(empty_repo):
    assert not empty_repo.is_dirty()
    assert not len(list(empty_repo.index.iter_blobs()))
    assert not len(empty_repo.branches)


def test_clean_repo(clean_repo):
    assert not clean_repo.is_dirty()
    assert clean_repo.statusline().endswith("[ \x1b[92mOK\x1b[39m ]") is True


def test_dirty_repo(dirty_repo):
    assert dirty_repo.is_dirty()
    assert dirty_repo.statusline().endswith("[ \x1b[91mKO\x1b[39m ]") is True


def test_dirty_index(dirty_index):
    assert dirty_index.is_dirty()
    assert dirty_index.statusline().endswith("[ \x1b[91mKO\x1b[39m ]") is True


def test_clean_repo2(clean_repo2):
    assert not clean_repo2.is_dirty()
    assert clean_repo2.statusline().endswith("[ \x1b[92mOK\x1b[39m ]") is True


def test_ignore(ignored_file):
    assert not ignored_file.is_dirty()


def test_cloned(clone):
    original, clone = clone
    assert original.remote_diff() == {}
    assert clone.remote_diff() == {"main": "2-1"}
    assert clone.statusline().endswith("(main:2-1) [ \x1b[92mOK\x1b[39m ]") is True


def test_stashed(stashed):
    assert stashed.stashed() is True
    assert (
        stashed.statusline().endswith("(\x1b[93mstash\x1b[39m) [ \x1b[92mOK\x1b[39m ]")
        is True
    )


def test_meta_discovery(meta, capsys):
    meta.discover()
    out, err = capsys.readouterr()
    assert out.startswith("Discovery of repositories")
    assert out.endswith("sub-directories\n")
    assert err == ""


@mark.skip
def test_meta_scan(meta, dirty_repo, capsys):

    meta.discover()
    # Purge of capsys, as discover is not the tested method here
    out, err = capsys.readouterr()

    meta.scan()
    out, err = capsys.readouterr()
    lines = out.splitlines()
    assert lines[0].endswith("(master:1) [ \x1b[92mOK\x1b[39m ]")
    assert lines[1].endswith(" \x1b[91mKO\x1b[39m ]")
    assert err == ""

    meta.scan(filter_status="OK")
    out, err = capsys.readouterr()
    assert out.endswith("(master:1) [ \x1b[92mOK\x1b[39m ]\n")

    meta.scan(filter_status="KO")
    out, err = capsys.readouterr()
    assert out.endswith("[ \x1b[91mKO\x1b[39m ]\n")

    meta.scan(filter_status="rdiff")
    out, err = capsys.readouterr()
    assert out.endswith("(master:1) [ \x1b[92mOK\x1b[39m ]\n")
