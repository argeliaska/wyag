import argparse
import collections
import configparser
from datetime import datetime
import grp, pwd
from fnmatch import fnmatch
import hashlib
from math import ceil
import os
import re
import sys
import zlib

from .gitrepository import repo_create, repo_find
from .gitobject_utils import object_read, object_find, object_hash
from .utils import log_graphviz

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


def main(argv=sys.argv[1:]):
    args = argparse.parse_args(argv)
    if   args.command == "add"          : pass
    elif args.command == "cat-file"     : cmd_cat_file(args)
    elif args.command == "check-ignore" : pass
    elif args.command == "checkout"     : pass
    elif args.command == "commit"       : pass
    elif args.command == "hash-object"  : cmd_hash_object(args)
    elif args.command == "init"         : cmd_init(args)
    elif args.command == "log"          : pass
    elif args.command == "ls-files"     : pass
    elif args.command == "merge"        : pass
    elif args.command == "rebase"       : pass
    elif args.command == "rev-parse"    : pass
    elif args.command == "rm"           : pass
    elif args.command == "show-ref"     : pass
    elif args.command == "status"       : pass
    elif args.command == "tag"          : pass
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
