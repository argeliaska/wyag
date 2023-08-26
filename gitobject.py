class GitObject(object):

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

