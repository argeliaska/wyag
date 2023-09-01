import os
import re
import zlib
import hashlib
import collections
from math import ceil

from .gitrepository import repo_dir, repo_file
from .gitobject import GitCommit, GitTree, GitTag, GitBlob, GitIndex, GitIndexEntry

def object_read(repo, sha):
    """ Read object sha from Git repository repo. Return a
     GitObject whose exact type depends on the object. """
    
    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if not os.path.isfile(path):
        return None
    
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())

        # Read object type
        x = raw.find(b' ')
        fmt = raw[0:x]

        # Read and validate object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw)-y-1:
            raise Exception("Malformed object {0}: bad length".format(sha))
        
        # Pick constructor
        if   fmt == b'commit' : c=GitCommit
        elif fmt == b'tree'   : c=GitTree
        elif fmt == b'tag'    : c=GitTag
        elif fmt == b'blob'   : c=GitBlob
        else                  : raise Exception("Unknown type {0} for object {1}".format(fmt.decode("ascii"), sha))

        # Call constructor and return object
        return c(raw[y+1:])
    
def object_find(repo, name, fmt=None, follow=True):
    # If we have a tag and fmt is anything else, we follow the tag.
    # If we have a commit and fmt is tree, we return this commit’s tree object
    # In all other situations, we bail out: nothing else makes sense.

    sha = object_resolve(repo, name)

    if not sha:
        raise Exception("No such reference {0}.".format(name))

    if len(sha) > 1:
        raise Exception("Ambiguos reference {0}: Candidates are:\n - {1}.".format(name, "\n - ".join(sha)))

    sha = sha[0]

    if not fmt:
        return sha
    
    while True:
        obj = object_read(repo, sha)
        # ^^^^^^^^ < this is a bit agressive: we're reading
        # the full object just to get its type. And we're doing
        # that in a loop, albeit normally short. Don't expect 
        # high performance here.

        if obj.fmt == fmt:
            return sha
        
        if not follow:
            return None
        
        # Follow tags
        if obj.fmt == b'tag':
            sha = obj.kvlm[b'object'].decode("ascii")
        elif obj.fmt == b'commit' and fmt == b'tree':
            sha = obj.kvlm[b'tree'].decode("ascii")
        else:
            return None
        
    
def object_write(obj, repo=None):
    # Serialize object data
    data = obj.serialize()
    # Add header
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    # Compute hash
    sha = hashlib.sha1(result).hexdigest()

    if repo:
        # Compute path
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)

        if not os.path.exists(path):
            with open(path, 'wb') as f:
                # Compress and write
                f.write(zlib.compress(result))
    
    return sha


def object_hash(fd, fmt, repo=None):
    """Hash object, writing it to repo if provided."""
    data = fd.read()

    # Choose constructor according to fmt argument
    if   fmt == b'commit' : obj=GitCommit(data)
    elif fmt == b'tree'   : obj=GitTree(data)
    elif fmt == b'tag'    : obj=GitTag(data)
    elif fmt == b'blob'   : obj=GitBlob(data)
    else                  : raise Exception("Unknown type %s!" % fmt)

    return object_write(obj, repo)


def object_resolve(repo, name):
    # This name resolution function will work like this:
    # If name is HEAD, it will just resolve .git/HEAD;
    # If name is a full hash, this hash is returned unmodified.
    # If name looks like a short hash, it will collect objects whose full hash begin with this short hash.
    # At last, it will resolve tags and branches matching name.
    #     
    """Resolve name to an object hash in repo.
    
    This function is aware of:

    - the HEAD literal
        - short and long hashes
        - tags
        - branches
        - remote branches"""
    candidates = list()
    hashRE = re.compile(r"^[0-9A-Fa-f]{4,40}$")

    # Empty string? Abort.
    if not name.strip():
        return None
    
    # Head is nonambiguos
    if name == "HEAD":
        return [ref_resolve(repo, "HEAD")]
    
    # If it's a hex string, try for a hash.
    if hashRE.match(name):
        # This may be a hash, either small of full. 4 seems to be the
        # minimal length for git to consider something a short hash.
        # This limit is documented in man git-rev-parse
        name = name.lower()
        prefix = name[0:2]
        path = repo_dir(repo, "objects", prefix, mkdir=False)
        if path:
            rem = name[2:]
            for f in os.listdir(path):
                if f.startswith(rem):
                    # Notice a string startswith() itself, so this
                    # works for full hashes.
                    candidates.append(prefix + f)
    
    # Try for references.
    as_tag = ref_resolve(repo, "refs/tags/" + name)
    if as_tag: # Did we find a tag?
        candidates.append(as_tag)

    as_branch = ref_resolve(repo, "refs/heads/" + name)
    if as_branch: # Did we find a branch?
        candidates.append(as_branch)

    return candidates
    


def ls_tree(repo, ref, recursive=None, prefix=""):
    sha = object_find(repo, ref, fmt=b"tree")
    obj = object_read(repo, sha)
    for item in obj.items:
        if len(item.mode) == 5:
            type = item.mode[0:1]
        else:
            type = item.mode[0:2]

        # Determine the type.
        if   type == b'04'   : type = "tree"
        elif type == b'10'   : type = "blob" # A regular file.
        elif type == b'12'   : type = "blob" # A symlink. Blob contents is link target.
        elif type == b'16'   : type = "commit" # A submodule
        else                 : raise Exception("Weird tree leaf mode {}".format(item.mode))

        if not (recursive and type=='tree'): # This is a leaf
            print("{0} {1} {2}\t{3}".format(
                "0" * (6 - len(item.mode)) + item.mode.decode("ascii"),
                # Git's ls-tree displays the type
                # of the object pointed to.  We can do that too :)
                type,
                item.sha, 
                os.path.join(prefix, item.path)
            ))
        else: # This is a branch, recurse
            ls_tree(repo, item.sha, recursive, os.path.join(prefix, item.path))


def ref_resolve(repo, ref):
    path = repo_file(repo, ref)

    # Sometimes, an inderect reference may be broken. This is normal
    # in one specific case: we're looking for HEAD on a new repository
    # with no commits. In that case, .git/HEAD points to "ref:
    # refs/heads/main", but .git/refs/heads/main doesn't exist yet
    # (since there's no commit for it to refer to).

    if not os.path.isfile(path):
        return None
    
    with open(path, 'r') as fp:
        data = fp.read()[:-1]
        # Drop final \n ^^^^^
    if data.startswith("ref: "):
        return ref_resolve(repo, data[5:])
    else:
        return data
    
def ref_list(repo, path=None):
    if not path:
        path = repo_dir(repo, "refs")
    ret = collections.OrderedDict()
    # Git show refs sorted. To do the same, we use
    # an OrderedDict and sort the output of listdir
    for f in sorted(os.listdir(path)):
        can = os.path.join(path, f)
        if os.path.isdir(can):
            ret[f] = ref_list(repo, can)
        else:
            ret[f] = ref_resolve(repo, can)

    return ret

def show_ref(repo, refs, with_hash=True, prefix=""):
    for k, v in refs.items():
        if type(v) == str:
            print("{0}{1}{2}".format(
                v + " " if with_hash else "",
                prefix + "/" if prefix else "",
                k))
        else:
            show_ref(repo, v, with_hash=with_hash, 
                     prefix="{0}{1}{2}".format(prefix, "/" if prefix else "", k))
        

def tag_create(repo, name, ref, create_tag_object=False):
    # get the GitObject from the object reference
    sha = object_find(repo, ref)

    if create_tag_object:
        # create tag object (commit)
        tag = GitTag(repo)
        tag.kvlm = collections.OrderedDict()
        tag.kvlm[b'object'] = sha.encode()
        tag.kvlm[b'type'] = b'commit'
        # Feel free to let the user give their name!
        # Notice you can fix this after commit, read on!
        tag.kvlm[b'tagger'] = b'Wyag <wyag@example.com>'
        # ...adn a tag message!
        tag.kvlm[None] = b"A tag generated by wyag, which won't let you customize the message!"
        tag_sha = object_write(tag)
        # create reference
        ref_create(repo, "tags/" + name, tag_sha)
    else:
        # create lightweight tag (ref)
        ref_create(repo, "tags/" + name, sha)


def ref_create(repo, ref_name, sha):
    with open(repo_file(repo, "refs/" + ref_name), 'w') as fp:
        fp.write(sha + "\n")



def index_read(repo):
    index_file = repo_file(repo, "index")

    # New repositories have no index!
    if not os.path.exists(index_file):
        return GitIndex()
    
    with open(index_file, 'rb') as f:
        raw = f.read()

    header = raw[:12]
    signature = header[:4]
    assert signature == b"DIRC" # Stands for "DirCache"
    version = int.from_bytes(header[4:8], "big")
    assert version == 2, "wyag only supports index file version 2"
    count = int.from_bytes(header[8:12], "big")

    entries = list()

    content = raw[12:]
    idx = 0
    for i in range(0, count):
        # Read creation time, as unix timestamp (seconds since)
        # 1970-01-01 00:00:00, the "epoch")
        ctime_s = int.from_bytes(content[idx: idx+4], "big")
        # Read creation time, as nanoseconds after that timestamps,
        # for extra precision.
        ctime_ns = int.from_bytes(content[idx+4: idx+8], "big") 
        # Same for modification time: first seconds from epoch.
        mtime_s = int.from_bytes(content[idx+8: idx+12], "big")
        # Then extra nanosecods
        mtime_ns = int.from_bytes(content[idx+12: idx+16], "big")
        # Device ID
        dev = int.from_bytes(content[idx+16: idx+20], "big")
        # Inode
        ino = int.from_bytes(content[idx+20: idx+24], "big")
        # Ignored.
        unused = int.from_bytes(content[idx+24: idx+26], "big")
        assert 0 == unused
        mode = int.from_bytes(content[idx+26: idx+28], "big")
        mode_type = mode >> 12
        assert mode_type in [0b1000, 0b1010, 0b1110]
        mode_perms = mode & 0b0000000111111111
        # User ID
        uid = int.from_bytes(content[idx+28: idx+32], "big")
        # Group ID
        gid = int.from_bytes(content[idx+32: idx+36], "big")
        # Size
        fsize = int.from_bytes(content[idx+36: idx+40], "big")
        # SHA (object ID). We'll store it as a lowercase hex string
        # for consistency.
        sha = format(int.from_bytes(content[idx+40: idx+60], "big"), "040x")
        # Flags we're going to ignore
        flags = int.from_bytes(content[idx+60: idx+62], "big")
        # Parse flags
        flag_assume_valid = (flags & 0b1000000000000000) != 0
        flags_extended = (flags & 0b0100000000000000) != 0
        assert not flags_extended
        flag_stage = flags & 0b0011000000000000
        # Length of the name. This is stored on 12 bits, some max
        # value is 0xFF, 4095. Since names can occasionally go 
        # beyond that length, git treats 0xFF as meaning at least
        # 0xFF, and looks for the final 0x00 to find the end of the
        # name --- at a small, and probably very rare, performance
        # cost.
        name_length = flags & 0b0000111111111111

        # We've read 62 bytes so far.
        idx += 62

        if name_length < 0xFFF:
            assert content[idx + name_length] == 0x00
            raw_name = content[idx:idx+name_length]
            idx += name_length + 1
        else:
            print("Notice: Name is 0x{:X} bytes long.".format(name_length))
            # TODO: This probably wasn't tested enough. It works with a 
            # path of exactly 0xFFF bytes. Any extra bytes broke
            # something between git, my shell and my filesystem.
            null_idx = content.find(b'\x00', idx + 0xFFF)
            raw_name = content[idx: null_idx]
            idx = null_idx + 1

        # Just parse the name as utf8
        name = raw_name.decode("utf8")

        # Data is padded on multiples of eight bytes for pointer
        # alignment, so we skip as many bytes as we need for the next
        # read to start at the right position.

        idx = 8 * ceil(idx / 8)

        # And we add this entry to our list.
        entries.append(GitIndexEntry(ctime=(ctime_s, ctime_ns),
                                     mtime=(mtime_s, mtime_ns),
                                     dev=dev,
                                     ino=ino,
                                     mode_type=mode_type,
                                     mode_perms=mode_perms,
                                     uid=uid,
                                     gid=gid,
                                     fsize=fsize,
                                     sha=sha,
                                     flag_assume_valid=flag_assume_valid,
                                     flag_stage=flag_stage,
                                     name=name))
        
        return GitIndex(version=version, entries=entries)
