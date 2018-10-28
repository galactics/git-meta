#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Check multiple git repositories' status

Usage:
  git-meta [-dc] [-a|-o|-n|-k|-r|-?]

Options:
  -d, --discover  Look for new git repositories
  -c, --clean     If a non-valid repository is encountered, it is removed from
                  the list
  -a, --all       Display all repositories
  -o, --ok        Display only repositories where everithing is fine
  -n, --nok       Display only repositories where there is something happening
  -k, --ko        Display only repositories where the working tree status is not
                  clean
  -r, --remote    Display only repositories needing some pushe with their
                  remotes
  -?, --unknown   Display only repositories in unknown state
  -h, --help      Show this help
  --version       Display the version of git-meta
"""

__version__ = "0.1.7"


import os
import re
import glob
import pygit2


class TagStr(str):
    """Tagged strings

    Allow you to decorate a bit your terminal output in a html fashion.
    Of course everything is not ported.

    Example:

    .. code-block:: python

        TagStr("Hello, I'm a <u>decorated</u> string")
        TagStr("What a coincidence, <color=green>me too</color>")
    """

    _shell = {
        "bold": ["\033[1m", "\033[21m"],
        "b": ["\033[1m", "\033[21m"],
        "underlined": ["\033[4m", "\033[24m"],
        "u": ["\033[4m", "\033[24m"],
        "reverse": ["\033[7m", "\033[27m"],
        "color": {
            "default": "\033[39m",
            "end": "\033[39m",
            "black": "\033[30m",
            "darkred": "\033[31m",
            "darkgreen": "\033[32m",
            "darkyellow": "\033[33m",
            "darkblue": "\033[34m",
            "darkmagenta": "\033[35m",
            "darkcyan": "\033[36m",
            "darkgray": "\033[90m",
            "gray": "\033[37m",
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "magenta": "\033[95m",
            "cyan": "\033[96m",
            "white": "\033[97m",
        },
        "end": "\033[0m",
    }

    def __add__(self, elem):
        """Concatenation handling

        >>> a = TagStr("Hello ")
        >>> b = "World"
        >>> type(a+b) is TagStr
        True
        >>> c = TagStr("World")
        >>> type(a+c) is TagStr
        True
        >>> a + 1
        Traceback (most recent call last):
            ...
        TypeError: TagStr concatenate only with str or TagStr
        """
        if not isinstance(elem, (str, self.__class__)):
            raise TypeError("TagStr concatenate only with str or TagStr")

        return self.__class__(str(self) + str(elem))

    def __radd__(self, elem):
        """Concatenation handling

        >>> a = "World"
        >>> b = TagStr("Hello ")
        >>> type(a+b) is TagStr
        True
        >>> c = TagStr("World")
        >>> type(c+b) is TagStr
        True
        >>> 1 + b
        Traceback (most recent call last):
            ...
        TypeError: TagStr concatenate only with str or TagStr
        """
        if not isinstance(elem, (str, self.__class__)):
            raise TypeError("TagStr concatenate only with str or TagStr")

        return self.__class__(str(elem) + str(self))

    def shell(self):
        """
        >>> test_str = TagStr('Here is a <u>test</u> string')
        >>> test_str
        'Here is a <u>test</u> string'
        >>> test_str.shell()
        'Here is a \\x1b[4mtest\\x1b[24m string'

        Returns:
            str: Convert the tags to a decorated shell output.
        """
        text = str(self)
        for tag, code in self._shell.items():
            if isinstance(code, dict):

                closing = self._shell["end"]

                # Determination of the closing tag
                if "end" in code.keys():
                    closing = self._shell[tag]["end"]

                for tag2, code2 in code.items():
                    regex = re.compile(
                        r"(<{0}={1}>)(.*?)(</{0}>)".format(tag, tag2), re.DOTALL
                    )
                    text = regex.sub(r"{0}\2{1}".format(code2, closing), text)
            else:
                regex = re.compile(r"(<{0}>)(.*?)(</{0}>)".format(tag), re.DOTALL)
                if isinstance(code, list):
                    text = regex.sub(r"{0}\2{1}".format(*code), text)
                else:
                    text = regex.sub(r"{0}\2{1}".format(code, self._shell["end"]), text)
        return text

    def empty(self):
        """
        >>> test_str = TagStr('Here is a <u>test</u> string')
        >>> test_str
        'Here is a <u>test</u> string'
        >>> test_str.empty()
        'Here is a test string'

        Returns:
            str: Refined string without tags
        """
        regex = re.compile(r"(<.*?>)")
        return regex.sub("", self)


class Repo(pygit2.Repository):
    """Class representing a repository.

    Allows to perform common git commands
    """

    def status(self):
        """Gives the status of the current branch.

        Contrarily to pygit2.Repository, self.status() does not show the
        ignored files.

        Returns:
            dict : Each key stand for a file with a non-clean status, and the
                value is the code of this non-clean status.
                See pygit2.GIT_STATUS_* for details.  If empty, all files are
                clean.
        """

        status = super(Repo, self).status()

        # As pygit2.Repository.status() gives also the status of ignored
        # files, we have to get rid of it ourselves.
        tmp = dict(status)
        for key, value in tmp.items():
            if value == pygit2.GIT_STATUS_IGNORED:
                del status[key]

        return status

    def remote_diff(self):
        """For each branch with a remote counterpart, give the number of
        commit difference

        Returns:
            dict: keys -> branch name
                values -> number
        """
        diffs = {}

        for branch_name in self.listall_branches(pygit2.GIT_BRANCH_LOCAL):
            branch = self.lookup_branch(branch_name)
            if branch.upstream is not None:
                remote = branch.upstream.peel()
                local = branch.peel()

                base = self.get(self.merge_base(local.id, remote.id))

                count_desc = 0
                # From local branch to base
                for commit in self.walk(local.id, pygit2.GIT_SORT_TOPOLOGICAL):
                    if commit.id == base.id:
                        break
                    count_desc += 1

                count_asc = 0
                # From remote branch to base
                for commit in self.walk(remote.id, pygit2.GIT_SORT_TOPOLOGICAL):
                    if commit.id == base.id:
                        break
                    count_asc += 1

                # Express remote difference in the '__git_ps1' fashion
                if count_asc or count_desc:
                    if count_asc and count_desc:
                        count = "{0}-{1}".format(count_desc, count_asc)
                    elif count_desc:
                        count = str(count_desc)
                    else:
                        count = str(-count_asc)

                    diffs[branch.shorthand] = count

        return diffs

    def stashed(self):
        """List stashes

        Returns:
            bool: True if there is stashed modifications
        """
        for ref in self.listall_references():
            if ref.startswith("refs/stash"):
                return True
        return False

    def statusline(self, line_width=80):
        """Create the status line for the selected repository.

        Returns:
            string: Status line as used by git-meta
        """

        form = {"filler": "", "more": []}

        max_path_len = line_width - 30

        template = " {path} {filler}{more} {status}"

        if self.is_bare:
            form["path"] = self.path
            form["more"] = ""
            form["status"] = "[<color=yellow>BARE</color>]"
        else:

            if len(self.workdir) <= max_path_len + 3:
                form["path"] = self.workdir
            else:
                form["path"] = "..." + self.workdir[-max_path_len:]

            if not self.status():
                form["status"] = "[ <color=green>OK</color> ]"
            else:
                form["status"] = "[ <color=red>KO</color> ]"

            remote_diff = self.remote_diff()
            if remote_diff:
                form["more"] = ["%s:%s" % tuple(x) for x in remote_diff.items()]

            if self.stashed():
                form["more"].append("<color=yellow>stash</color>")

            if len(form["more"]):
                form["more"] = "(" + ",".join(form["more"]) + ")"
            else:
                form["more"] = ""

        line = TagStr(template.format(**form))
        form["filler"] = " " * (line_width - len(line.empty()))

        line = TagStr(template.format(**form))
        return line.shell()


class Meta(object):
    """Class handling the repositories database"""

    def __init__(self):
        self.repolist = []

        self._define_paths()
        # Load the database file
        try:
            self.read_list()
        except (IOError, FileNotFoundError):
            self.discover()

    def _define_paths(self):

        # Default locations
        self.config = {
            "repolist": os.path.join(os.environ["HOME"], ".git_meta_repolist"),
            "ignorelist": os.path.join(os.environ["HOME"], ".git_meta_ignore"),
            "scanroot": os.environ["HOME"],
        }

        # Parsing of the global config file
        try:
            global_config = pygit2.Config.get_global_config()
        except (IOError, FileNotFoundError):
            pass
        else:
            for fullkey in global_config:

                # If the config item does not start with meta it's ignored
                if not fullkey.name.startswith("meta"):
                    continue

                key = fullkey.name.partition(".")[2]

                if key in self.config.keys():
                    self.config[key] = global_config[fullkey.name]

    def read_list(self):
        """Read the database file to extract the paths of previously scanned
        repositories
        """

        with open(self.config["repolist"]) as repolist_f:
            self.repolist = repolist_f.read().splitlines()

    def discover(self):
        """Scan the subfolders to discover repositories
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
                except pygit2.GitError:
                    # This is not a valid git repository
                    continue
                else:
                    # Success !!
                    repolist.append(repo.path)

                    # In case of found repository it's not necessary
                    # to digg deeper.
                    # Thus, we avoid the struggle of handling submodules
                    # which are perfectly managed by the base repository.
                    del dirs[:]

        self._write_repolist(repolist)

        # Force the content of the repolist to the newly made
        self.repolist = sorted(set(repolist))

    def _write_repolist(self, repolist):
        """Writing all the repositories discovered to the database
        file for future utilisation

        Args:
            repolist (list of str)
        """
        with open(self.config["repolist"], "w+") as repofile:
            repofile.write("\n".join(repolist))

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

        for path in self.repolist:
            try:
                repo = Repo(path)
            except pygit2.GitError:
                errstr = TagStr(
                    " <color=red>%s\n    is not a valid repository</color>" % path
                )
                print(errstr.shell())
                if clean:
                    repolist = self.repolist[:]
                    repolist.remove(path)
                    self._write_repolist(repolist)
            else:
                if (
                    filter_status in (None, "all")
                    or (filter_status == "OK" and not repo.status())
                    or (filter_status == "KO" and repo.status())
                    or (filter_status == "remote" and repo.remote_diff())
                    or (
                        filter_status == "NOK" and (repo.status() or repo.remote_diff())
                    )
                ):
                    print(repo.statusline(line_width))


def main():  # pragma: no cover
    """Main ``git-meta`` script function """

    from docopt import docopt
    import pkg_resources

    args = docopt(__doc__, version=__version__)

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

    meta = Meta()
    if args["--discover"]:
        meta.discover()
    meta.scan(filter_status=filter_status, clean=args["--clean"])
