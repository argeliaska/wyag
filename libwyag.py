import argparse
from datetime import datetime
import grp, pwd
import os
import sys

from .gitrepository import repo_create, repo_find
from .gitobject_utils import object_read, object_find, object_hash, ls_tree, \
                             ref_list, show_ref, tag_create, index_read, \
                             gitignore_read, check_ignore, tree_from_index, repo_file
from .utils import log_graphviz, branch_get_active, tree_to_dict, rm, add, commit_create, gitconfig_read, gitconfig_user_get

argparse = argparse.ArgumentParser(description="The stupidest content tracker")

# you don't just call git, you call git COMMAND
argsubparsers = argparse.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True

# INIT 
argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository.")
argsp.add_argument("path", 
                   metavar="directory", 
                   nargs="?", 
                   default=".", 
                   help="Where to create the repository.")

# CAT-FILE
argsp = argsubparsers.add_parser("cat-file", help="Provide content of repository objects.")
argsp.add_argument("type", 
                   metavar="type", 
                   choices=["blob", "commit", "tag", "tree"], 
                   help="Specify the type")

argsp.add_argument("object", 
                   metavar="object", 
                   help="The object to display")

# HASH-OBJECT
argsp = argsubparsers.add_parser("hash-object", help="Compute object ID and optionally creates a blob from a file")
argsp.add_argument("-t", 
                   metavar="type",
                   dest="type", 
                   choices=["blob", "commit", "tag", "tree"], 
                   default="blob",
                   help="Specify the type")

argsp.add_argument("-w", 
                   dest="write",
                   action="store_true",  
                   help="Actually write the object into the database")

argsp.add_argument("path", 
                   help="Read object from <file>")

argsp = argsubparsers.add_parser("log", help="Display history of a given commit.")
argsp.add_argument("commit",
                   default="HEAD",
                   nargs="?",
                   help="Commit to start at.")

# LS-TREE
argsp = argsubparsers.add_parser("ls-tree", help="Pretty-print a tree object.")
argsp.add_argument("-r", 
                   dest="recursive", 
                   action="store_true",
                   help="Recurse into sub-trees")

argsp.add_argument("tree", 
                   help="A tree-ish object")

# CHECKOUT
argsp = argsubparsers.add_parser("checkout", help="Checkout a commit inside of a directory.")
argsp.add_argument("commit", 
                   help="The commit or tree to checkout.")
argsp.add_argument("path", 
                   help="The EMPTY directory to checkout on.")

# SHOW-REF
argsp = argsubparsers.add_parser("show-ref", help="List references.")

# TAG
argsp = argsubparsers.add_parser("tag", help="List and create tags")
argsp.add_argument("-a",
                   action="store_true",
                   dest="create_tag_object",
                   help="Wheter to create a tag object")
argsp.add_argument("name", 
                   nargs="?",
                   help="The new tag's name")
argsp.add_argument("object",
                   default="HEAD",
                   nargs="?",
                   help="The object the new tag will point to")

# REV-PARSE
argsp = argsubparsers.add_parser("rev-parse", help="Parse revision (or other objects) identifiers")
argsp.add_argument("--wayg-type",
                   metavar="type",
                   dest="type",
                   choices=["blob", "commit", "tag", "tree"],
                   default=None,
                   help="Specify the expected type")
argsp.add_argument("name",
                   help="The name to parse")


# LS-FILES
argsp = argsubparsers.add_parser("ls-files", help="List all the stage files")
argsp.add_argument("--verbose", action="store_true", help="Show everything.")

# CHECK-IGNORE
argsp = argsubparsers.add_parser("check-ignore", help="Check path(s) against ignore rules.")
argsp.add_argument("path", nargs="+", help="Paths to check")

# STATUS
argsp = argsubparsers.add_parser("status", help="Show the working tree status.")

# RM
argsp = argsubparsers.add_parser("rm", help="Remove files from the working tree and the index.")
argsp.add_argument("path", nargs="+", help="Files to remove")

# ADD
argsp = argsubparsers.add_parser("add", help="Add files contents to the index.")
argsp.add_argument("path", nargs="+", help="Files to add")

# COMMIT
argsp = argsubparsers.add_parser("commit", help="Record changes to the repository")
argsp.add_argument("-m",
                   metavar="message",
                   dest="message",
                   help="Message to associate with this commit.")



def main(argv=sys.argv[1:]):
    args = argparse.parse_args(argv)
    if   args.command == "add"          : cmd_add(args)
    elif args.command == "cat-file"     : cmd_cat_file(args)
    elif args.command == "check-ignore" : cmd_check_ignore(args)
    elif args.command == "checkout"     : cmd_checkout(args)
    elif args.command == "commit"       : cmd_commit(args)
    elif args.command == "hash-object"  : cmd_hash_object(args)
    elif args.command == "init"         : cmd_init(args)
    elif args.command == "log"          : cmd_log(args)
    elif args.command == "ls-files"     : cmd_ls_files(args)
    elif args.command == "ls-tree"      : cmd_ls_tree(args)
    elif args.command == "merge"        : pass
    elif args.command == "rebase"       : pass
    elif args.command == "rev-parse"    : cmd_rev_parse(args)
    elif args.command == "rm"           : cmd_rm(args)
    elif args.command == "show-ref"     : cmd_show_ref(args)
    elif args.command == "status"       : cmd_status(args)
    elif args.command == "tag"          : cmd_tag(args)
    else                                : print("Bad command.")


def cmd_init(args):
    repo_create(args.path)

def cmd_cat_file(args):
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())

def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())

def cmd_hash_object(args):
    if args.write:
        repo = repo_find()
    else:
        repo = None
    
    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)

def cmd_log(args):
    """ A simpler version of Git log """

    repo = repo_find()

    print("digraph wyaglog{")
    print("  node[shape=rect]")
    # we’ll dump Graphviz data and let the user use dot to render the actual log.
    log_graphviz(repo, object_find(repo, args.commit), set())
    print("}")

def cmd_ls_tree(args):
    repo = repo_find()
    ls_tree(repo, args.tree, args.recursive)

def cmd_checkout(args):
    repo = repo_find()

    obj = object_read(repo, object_find(repo, args.commit))

    # If the object is a commit, we grab its tree
    if obj.fmt == b'commit':
        obj = object_read(repo, obj.kvlm[b'tree'].decode("ascii"))

    # Verify that path is an empty directory
    if os.path.exists(args.path):
        if not os.path.isdir(args.path):
            raise Exception("Not a directory {0}!".format(args.path))
        if os.listdir(args.path):
            raise Exception("Not empty {0}!".format(args.path))
    else:
        os.makedirs(args.path)

    tree_checkout(repo, obj, os.path.realpath(args.path))

def tree_checkout(repo, tree, path):
    for item in tree.items:
        obj = object_read(repo, item.sha)
        dest = os.path.join(repo, item.path)

        if obj.fmt == b'tree':
            os.mkdir(dest)
            tree_checkout(repo, obj, dest)
        elif obj.fmt == b'blob':
            # @TODO Support symlinks (identified by mode 12****)
            with open(dest, 'wb') as f:
                f.write(obj.blobdata)

def cmd_show_ref(args):
    repo = repo_find()
    refs = ref_list(repo)
    show_ref(repo, refs, prefix="refs")


def cmd_tag(args):
    repo = repo_find()

    if args.name:
        tag_create(repo, 
                   args.name, 
                   args.object,
                   type="object" if args.create_tag_object else "ref")
    else:
        refs = ref_list(repo)
        show_ref(repo, refs["tags"], with_hash=False)


def cmd_rev_parse(args):
    # We’re going to clone only one use cases of the rev-parse command: solving references
    if args.type:
        fmt = args.type.encode()
    else:
        fmt = None

    repo = repo_find()

    print(object_find(repo, args.name, fmt, follow=True))

def cmd_ls_files(args):
    repo = repo_find()
    index = index_read(repo)
    if args.verbose:
        print("Index file format v{}, containing {} entries.".format(index.version, len(index.entries)))

    for e in index.entries:
        print(e.name)
        if args.verbose:
            print("  {} with perms: {:o}".format(
                { 0b1000: "regular file",
                  0b1010: "symlink",
                  0b1110: "git link" }[e.mode_type],
                e.mode_perms))
            print("  on blob: {}".format(e.sha))
            print("  created: {}.{}, modified: {}.{}".format(
                datetime.fromtimestamp(e.ctime[0])
                , e.ctime[1]
                , datetime.fromtimestamp(e.mtime[0])
                , e.mtime[1]))
            print("  devide: {}, inode: {}".format(e.dev, e.ino))
            print("  user: {} ({})  group: {} ({})".format(
                pwd.getpwuid(e.uid).pw_name,
                e.uid,
                grp.getgrgid(e.gid).gr_name,
                e.gid))
            print("  flags: stage={} assume_valid={}".format(
                e.flag_stage,
                e.flag_assume_valid))
            

def cmd_check_ignore(args):
    repo = repo_find()
    rules = gitignore_read(repo)
    for path in args.path:
        if check_ignore(rules, path):
            print(path)


def cmd_status(_):
    repo = repo_find()
    index = index_read(repo)

    cmd_status_branch(repo)
    # cmd_status_head_index(repo, index)
    # print()
    # cmd_status_index_worktree(repo, index)


def cmd_status_branch(repo):
    branch = branch_get_active(repo)
    if branch:
        print("On branch {}.".format(branch))
    else:
        print("HEAD detached at {}.".format(object_find(repo, "HEAD")))


def cmd_status_head_index(repo, index):
    print("Changes to be commited:")

    head = tree_to_dict(repo, "HEAD")
    for entry in index.entries:
        if entry.name in head:
            if head[entry.name] != entry.sha:
                print("  modified:", entry.name)
            del head[entry.name] # Delete the key
        else:
            print("  added:  ", entry.name)
    
    # Keys still in HEAD are files that we haven't met in the index,
    # and thus have been deleted.
    for entry in head.keys():
        print("  deleted: ", entry)


def cmd_status_index_worktree(repo, index):
    print("Changes not staged for commit:")

    ignore = gitignore_read(repo)

    gitdir_prefix = repo.gitdir + os.path.sep

    all_files = list()

    # We begin by walking the filesystem
    for (root, _, files) in os.walk(repo.worktree, True):
        if root==repo.gitdir or root.startswith(gitdir_prefix):
            continue
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, repo.worktree)
            all_files.append(rel_path)

    # We now traverse the index, and compare real files with the cached
    # versions.

    for entry in index.entries:
        full_path = os.path.join(repo.worktree, entry.name)

        # That file *name* is in the index

        if not os.path.exists(full_path):
            print("  deleted: ", entry.name)
        else:
            stat = os.stat(full_path)

            # Compare metadata
            ctime_ns = entry.ctime[0] * 10**9 + entry.ctime[1]
            mtime_ns = entry.mtime[0] * 10**9 + entry.mtime[1] 
            if (stat.st_ctime_ns != ctime_ns) or (stat.st_mtime_ns != mtime_ns):
                # If different, deep compare.
                # @FIXME This *will* crash on symlinks to dir.
                with open(full_path, "rb") as fd:
                    new_sha = object_hash(fd, b"blob", None)
                    # If the hashes are the same, the files are actually the same.
                    same = entry.sha == new_sha

                    if not same:
                        print("  modified:", entry.name)
        if entry.name in all_files:
            all_files.remove(entry.name)

        print()
        print("Untracked files:")

        for f in all_files:
            # @TODO If a full directory is untracked, we should display
            # its name without its contents.
            if not check_ignore(ignore, f):
                print(" ", f)


def cmd_rm(args):
    repo = repo_find()
    rm(repo, args.path)

def cmd_add(args):
    repo = repo_find()
    add(repo, args.path)


def cmd_commit(args):
    repo = repo_find()
    index = index_read(repo)
    # Creates trees, grab back SHA for the root tree.
    tree = tree_from_index(repo, index)

    # Create the commit object itself
    commit = commit_create(repo,
                           tree, 
                           object_find(repo, "HEAD"),
                           gitconfig_user_get(gitconfig_read()),
                           datetime.now(),
                           args.message)

    # Update HEAD so our commit is now the top of the active branch.
    active_branch = branch_get_active(repo)
    if active_branch: # If we're on a branch, we update refs/heads/BRANCH
        with open(repo_file(repo, os.path.join("refs/heads", active_branch)), "w") as fd:
            fd.write(commit + "\n")
    else: # Otherwise, we update HEAD itself.
        with open(repo_file(repo, "HEAD"), "w") as fd:
            fd.write("\n")