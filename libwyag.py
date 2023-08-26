import argparse
import collections
from datetime import datetime
import grp, pwd
from fnmatch import fnmatch
import hashlib
from math import ceil
import os
import re
import sys
import zlib

from .gitrepository import repo_create


argparse = argparse.ArgumentParser(description="The stupidest content tracker")

# you don't just call git, you call git COMMAND
argsubparsers = argparse.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True

argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository.")
argsp.add_argument("path", 
                   metavar="directory", 
                   nargs="?", 
                   default=".", 
                   help="Where to create the repository.")

def main(argv=sys.argv[1:]):
    args = argparse.parse_args(argv)
    if   args.command == "add"          : pass
    elif args.command == "cat-file"     : pass
    elif args.command == "check-ignore" : pass
    elif args.command == "checkout"     : pass
    elif args.command == "commit"       : pass
    elif args.command == "hash-object"  : pass
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