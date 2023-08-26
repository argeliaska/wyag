import os
import zlib
import hashlib
from .gitrepository import repo_file
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
    return name    
    
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