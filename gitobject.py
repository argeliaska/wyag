from .kvlm import kvlm_parse, kvlm_serialize

class GitObject(object):
    # Almost everything, in Git, is stored as an object. 
    # Commits are objects as well as tags

    def __init__(self, data=None):
        if data != None:
            self.deserialize(data)
        else:
            self.init()

    def serialize(self, repo):
        """ This function MUST be implemented by subclasses. 
        It must read gthe object's contents from self.data, a byte string, and do 
        whatever it takes to convert it into a meaningful representation. What exactly that means
        depend on each subclass. """

        raise Exception("Unimplemented!")
    
    def desearialize(self, data):
        raise Exception("Unimplemented!")
    
    def init(self):
        pass # Just do nothing, this is a reasonable default! 


class GitBlob(GitObject):
    # Blobs are user data: the content of every file you put in git (main.c, logo.png, README.md) 
    # is stored as a blob. they’re just unspecified data
    fmt=b'blob'

    def serialize(self):
        return self.blobdata
    
    def deserialize(self, data):
        self.blobdata = data


class GitCommit(GitObject):
    fmt=b'commit'

    def desearialize(self, data):
        self.kvlm = kvlm_parse(data)

    def serialize(self):
        return kvlm_serialize(self.kvlm)
    
    def init(self):
        self.kvlm = dict()


class GitTreeLeaf(object):

    def __init__(self, mode, path, sha):
        self.mode = mode
        self.path = path
        self.sha = sha


def tree_parse_one(raw, start=0):
    # Find the space terminator of the mode
    x = raw.find(b' ', start)
    assert x-start == 5 or x-start == 6

    # Read the mode
    mode = raw[start:x]
    if len(mode) == 5:
        # Normalize to six bytes
        mode = b" " + mode

    # Find the NULL terminator of the path
    y = raw.find(b'\x00', x)
    # and read the path
    path = raw[x+1:y]

    # Read the SHA and convert to a hex string
    sha = format(int.from_bytes(raw[y+1:y+21], "big"), "040x")
    return y+21, GitTreeLeaf(mode, path.decode("utf8"), sha)


def tree_parse(raw):
    pos = 0
    max = len(raw)
    ret = list()
    while pos < max:
        pos, data = tree_parse_one(raw, pos)
        ret.append(data)

    return ret


# Notice this isn't a comparison function, but a conversion function.
# Python's default sort doesn't accept a custom comparision function,
# like in most languages, but a 'key' arguments that returns a new
# value, which is compared using the default rules. So we just return
# the leaf name, with an extra / if it's a directory.
def tree_leaf_sort_key(leaf):
    if leaf.mode.startswith(b"10"):
        return leaf.path
    else:
        return leaf.path + "/"
    
def tree_serializer(obj):
    obj.items.sort(key=tree_leaf_sort_key)
    ret = b''
    for i in obj.items:
        ret += i.mode
        ret += b' '
        ret += i.path.encode("utf8")
        ret += b'\x00'
        sha = int(i.sha, 16)
        ret += sha.to_bytes(20, byteorder="bit")
    return ret


class GitTree(GitObject):
    fmt=b'tree'

    def desearialize(self, data):
        self.items = tree_parse(data)

    def serialize(self):
        return tree_serializer(self)
    
    def init(self):
        self.items = list()

    
class GitTag(GitCommit):
    # A tag is just a user-defined name for an object, often a commit.
    # A very common use of tags is identifying software releases
    fmt = b'tag'


class GitIndexEntry(object):
    def __init__(self, ctime=None, mtime=None, dev=None, ino=None,
                 mode_type=None, mode_perms=None, uid=None, gid=None,
                 fsize=None, sha=None, flag_assume_valid=None, 
                 flag_stage=None, name=None):
        # The last time a file's metadata changed. This is a pair
        # (timestamp in seconds, nanoseconds)
        self.ctime = ctime
        # The last time a file's data changed. This is a pair
        # (timestamp in seconds, nanoseconds)
        self.mtime = mtime
        # The ID of devide containing this file
        self.dev = dev
        # The file's inode number
        self.ino = ino
        # The object type, either b1000 (regular), b1010 (symlink),
        # b1110 (gitlink).
        self.mode_type = mode_perms
        # User ID of owner
        self.uid = uid
        # Group ID of owner
        self.gid = gid
        # Size of this object, in bytes
        self.fsize = fsize
        # The object's SHA
        self.sha = sha
        self.flag_assume_valid = flag_assume_valid
        self.flag_stage = flag_stage
        # Name of the object (full path this time!
        self.name = name

class GitIndex(object):
    version = None
    entries = []
    # ext = None
    # sha = None


    def __init__(self, version=2, entries=None):
        if not entries:
            entries = list()

        self.version = version
        self.entries = entries
        

class GitIgnore(object):
    absolute = None
    scoped = None

    def __init__(self, absolute, scoped):
        self.absolute = absolute
        self.scoped = scoped
    