import os
import re
import zlib
import hashlib
import collections
from .gitrepository import repo_dir, repo_file
from .gitobject import GitCommit, GitTree, GitTag, GitBlob

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
