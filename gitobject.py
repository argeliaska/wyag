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

