class AuthError(Exception):
    """
    Custom authentication error class to replace the missing gotrue.AuthError
    """
    def __init__(self, message="Authentication error", code=None, status=400):
        self.message = message
        self.code = code
        self.status = status
        super().__init__(self.message) 