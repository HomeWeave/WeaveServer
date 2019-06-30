

class BaseAuthorizer(object):
    def authorize(self, app_url, operation, channel):
        raise NotImplementedError


class AllowAllAuthorizer(BaseAuthorizer):
    def authorize(self, app_url, operation, channel):
        return True


class WhitelistAuthorizer(BaseAuthorizer):
    def __init__(self, whitelisted_urls):
        self.allowed_app_urls = whitelisted_urls

    def authorize(self, app_url, operation, channel):
        return operation == "enqueue" and app_url in self.allowed_app_urls


class DequeueAuthorizer(BaseAuthorizer):
    def __init__(self, whitelisted_urls):
        self.allowed_app_urls = whitelisted_urls

    def authorize(self, app_url, operation, channel):
        return operation == "dequeue" and app_url in self.allowed_app_urls


class ChainedAuthorizer(BaseAuthorizer):
    def __init__(self, authorizers):
        self.authorizers = authorizers

    def authorize(self, app_url, operation, channel):
        for authorizer in self.authorizers:
            if authorizer.authorize(app_url, operation, channel):
                return True

        return False
