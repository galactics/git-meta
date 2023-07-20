#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Check multiple git repositories' status

Usage:
  git-meta [-dc] [-a|-o|-n|-k|-r|-?|--no-remote] [-t]

Options:
  -d, --discover  Look for new git repositories
  -c, --clean     If a non-valid repository is encountered, it is removed from
                  the list
  -a, --all       Display all repositories
  -o, --ok        Display only repositories where everithing is fine
  -n, --nok       Display only repositories where there is something happening
  -k, --ko        Display only repositories where the working tree status is not
                  clean
  -r, --remote    Display only repositories needing some pushes with their
                  remotes
  --no-remote     List repositories having no remote set
  -?, --unknown   Display only repositories in unknown state
  -t, --terminal  Open terminals for each selected repository
  -h, --help      Show this help
  --version       Display the version of git-meta
  --pdb           Launch debugger when crashing
"""

__version__ = "0.2.3"


import os
import re
import git
import glob
import logging
import subprocess
from pathlib import Path
from appdirs import user_cache_dir
from rich.console import Console
from rich.text import Text

console = Console()
log = logging.getLogger(__name__)


def pm_on_crash(type, value, tb):
    """Exception hook, in order to start pdb when an exception occurs"""
    import pdb
    import traceback

    traceback.print_exception(type, value, tb)
    pdb.pm()


class Repo(git.Repo):
    """Class representing a repository.

    Allows to perform common git commands
    """

    def is_dirty(self):
        """Override of git.Repo.is_dirty to include untracked files in dirty state"""
        return super().is_dirty() or len(self.untracked_files) != 0

    def remote_diff(self):
        """For each branch with a remote counterpart, give the number of
        commit difference

        Returns:
            dict: keys -> branch name
                values -> number
        """
        diffs = {}

        remote_refs = set([br for rem in self.remotes for br in rem.refs])

        for branch in self.branches:
            if branch.tracking_branch() is not None:
                remote = branch.tracking_branch()

                # Check if the remote branch is available in any remote
                # branches. When a remote branch is deleted but the local
                # branch is kept, the remote branch still appears as tracking
                # branch, even so it does not exist as a reference anymore
                # See issue https://github.com/galactics/git-meta/issues/1
                if remote not in remote_refs:
                    continue

                base = self.merge_base(branch, remote)[0]

                # From base to local branch
                count_desc = len(
                    list(
                        self.iter_commits(
                            "{}..{}".format(base.hexsha, branch.commit.hexsha)
                        )
                    )
                )
                # From base to remote branch
                count_asc = len(
                    list(
                        self.iter_commits(
                            "{}..{}".format(base.hexsha, remote.commit.hexsha)
                        )
                    )
                )

                # Express remote difference in the '__git_ps1' fashion
                if count_asc or count_desc:
                    if count_asc and count_desc:
                        count = "+{0}-{1}".format(count_desc, count_asc)
                    elif count_desc:
                        count = "{0:+0}".format(count_desc)
                    else:
                        count = "{0:+0}".format(-count_asc)

                    diffs[branch.name] = count

        return diffs

    def has_remote(self):
        """
        Return:
            bool: True if the repository has a remote branch defined for at least
                local branch
        """
        for branch in self.branches:
            if branch.tracking_branch() is not None:
                return True
        else:
            return False

    def stashed(self):
        """List stashes

        Returns:
            bool: True if there is stashed modifications
        """
        return len(self.git.stash("list")) > 0

    def statusline(self, line_width=80):
        """Create the status line for the selected repository.

        Returns:
            string: Status line as used by git-meta
        """

        form = {"filler": "", "more": []}

        max_path_len = line_width - 30

        template = " {path} {filler}{more} {status}"

        if self.bare:
            form["path"] = self.path
            form["more"] = ""
            form["status"] = r"[[bright_yellow]BARE[bright_yellow]]"
        else:
            if len(self.working_dir) <= max_path_len + 3:
                form["path"] = self.working_dir
            else:
                form["path"] = "..." + self.working_dir[-max_path_len:]

            if not self.is_dirty():
                form["status"] = r"[ [bold bright_green]OK[/bold bright_green] ]"
            else:
                form["status"] = r"[ [bold bright_red]KO[/bold bright_red] ]"

            remote_diff = self.remote_diff()
            if remote_diff:
                form["more"] = [
                    f"{k}[bright_green]{v}[/bright_green]"
                    for k, v in remote_diff.items()
                ]

            if self.stashed():
                form["more"].append("[bright_yellow]stash[/bright_yellow]")

            if len(form["more"]):
                form["more"] = "(" + ",".join(form["more"]) + ")"
            else:
                form["more"] = ""

        line = template.format(**form)
        line_len = Text.from_markup(line).cell_len
        form["filler"] = " " * (line_width - line_len)

        line = template.format(**form)
        return line


class Meta(object):
    """Class handling the repositories database"""

    def __init__(self):
        self._define_paths()
        # Load the database file

        if not self.repolist:
            self.discover()

    def _define_paths(self):
        cache = user_cache_dir("gitmeta", "gitmeta")

        # Default locations
        self.config = {
            "repolist": os.path.join(cache, "repolist.txt"),
            "ignorelist": os.path.join(cache, "ignore.txt"),
            "scanroot": os.environ["HOME"],
        }

        # Parsing of the global config file
        try:
            global_config = git.config.GitConfigParser(config_level="global")
        except (IOError, FileNotFoundError):
            pass
        else:
            if global_config.has_section("meta"):
                for k, v in global_config.items("meta"):
                    self.config[k] = v

    @property
    def repolist(self):
        """Read the database file to extract the paths of previously scanned
        repositories
        """

        if not hasattr(self, "_repolist"):
            try:
                with open(self.config["repolist"]) as repolist_f:
                    self._repolist = repolist_f.read().splitlines()
            except (IOError, FileNotFoundError):
                self._repolist = []

        return self._repolist

    @repolist.setter
    def repolist(self, repolist):
        """Writing all the repositories discovered to the database
        file for future utilisation

        Args:
            repolist (list of str)
        """

        repolist = list(sorted(repolist))

        os.makedirs(os.path.dirname(self.config["repolist"]), exist_ok=True)

        with open(self.config["repolist"], "w+") as repofile:
            repofile.write("\n".join(repolist))

        self._repolist = repolist

    def discover(self):
        """Scan the subfolders to discover repositories

        The root folder can be defined with the ``meta.scanroot`` field
        in your .gitconfig file. If not defined, the default scanroot
        is $HOME.
        """

        try:
            with open(self.config["ignorelist"]) as ignore_file:
                ignorelist = ignore_file.read().splitlines()
        except (IOError, FileNotFoundError):
            ignorelist = []

        repolist = []

        print(
            "Discovery of repositories in {0} sub-directories".format(
                self.config["scanroot"]
            )
        )

        for root, dirs, files in os.walk(self.config["scanroot"]):
            if root in ignorelist:
                # we also want to ignore every subfolder
                del dirs[:]
                continue

            # Check for globing pattern match to ignore
            for ignore_path in ignorelist:
                if glob.has_magic(ignore_path) and glob.fnmatch.fnmatch(
                    root, ignore_path
                ):
                    del dirs[:]
                    continue

            if ".git" in dirs or "config" in files:
                # It looks like a repository, but is it?
                try:
                    repo = Repo(root)
                except git.exc.GitError:
                    # This is not a valid git repository
                    continue
                else:
                    # Success !!
                    repolist.append(repo.working_dir)

                    # In case of found repository it's not necessary
                    # to digg deeper.
                    # Thus, we avoid the struggle of handling submodules
                    # which are perfectly managed by the base repository.
                    del dirs[:]

        self.repolist = repolist

    def iter(self, clean=False, filter_status=None):
        errstr = ""
        for path in self.repolist.copy():
            try:
                repo = Repo(path)
            except git.exc.GitError:
                errstr = f"[bright_red]{path}[/bright_red]"
                if clean:
                    errstr += " discarded"
                else:
                    errstr += " is not a valid repository."
                console.print(errstr)
                if clean:
                    new_repolist = self.repolist.copy()
                    new_repolist.remove(path)
                    self.repolist = new_repolist
            else:
                if (
                    filter_status in (None, "all")
                    or (filter_status == "OK" and not repo.is_dirty())
                    or (filter_status == "KO" and repo.is_dirty())
                    or (filter_status == "remote" and repo.remote_diff())
                    or (filter_status == "no-remote" and not repo.has_remote())
                    or (
                        filter_status == "NOK"
                        and (repo.is_dirty() or repo.remote_diff() or repo.stashed())
                    )
                ):
                    yield repo
        if not clean and errstr:
            print("\nUse the --clean option to discard invalid repositories.")

    def scan(self, clean=False, filter_status=None):
        """Scan all the repositories in the database for their statuses

        Args:
            clean (bool): If True, remove any unvalid repository from the watched list
            filter_status (str): Only return repositiries having the given status.
                Usable status are "OK", "KO", "remote", "NOK" and "all"
        """

        try:
            _, column = os.popen("stty size", "r").read().split()
            line_width = int(column)
        except Exception:
            line_width = 80

        for repo in self.iter(clean=clean, filter_status=filter_status):
            console.print(repo.statusline(line_width), highlight=False)

    def terminal(self, filter_status=None):
        """Open a terminal on each repository selected by the filter

        see :meth:`Meta.scan` for details on filter_status
        """
        try:
            terminal = self.config["terminal"].split()
        except KeyError:
            print("No terminal defined. set the meta.terminal field in your .gitconfig")
        else:
            for repo in self.iter(filter_status=filter_status):
                subprocess.Popen(
                    [*terminal, repo.working_dir],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )


def main():  # pragma: no cover
    """Main ``git-meta`` script function"""

    import sys
    from docopt import docopt

    if "--pdb" in sys.argv:
        sys.argv.remove("--pdb")
        func = pm_on_crash

    args = docopt(__doc__, version=__version__)

    # print(args)

    filter_status = "NOK"  # default behaviour
    if args["--all"]:
        filter_status = "all"
    elif args["--ok"]:
        filter_status = "OK"
    elif args["--nok"]:
        filter_status = "NOK"
    elif args["--ko"]:
        filter_status = "KO"
    elif args["--remote"]:
        filter_status = "remote"
    elif args["--unknown"]:
        filter_status = "?"
    elif args["--no-remote"]:
        filter_status = "no-remote"

    meta = Meta()
    if args["--discover"]:
        meta.discover()

    meta.scan(filter_status=filter_status, clean=args["--clean"])

    if args["--terminal"]:
        meta.terminal(filter_status=filter_status)


if __name__ == "__main__":
    main()
