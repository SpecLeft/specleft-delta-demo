class DocumentError(Exception):
    pass


class NotFoundError(DocumentError):
    pass


class InvalidTransitionError(DocumentError):
    pass


class PermissionError(DocumentError):
    pass


class ValidationError(DocumentError):
    pass
