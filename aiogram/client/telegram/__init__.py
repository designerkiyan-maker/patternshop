class TelegramAPIServer:
    DEFAULT = "https://api.telegram.org"
    def __init__(self, base=None, is_test=False):
        self._base = base or self.DEFAULT
        self.is_test = is_test
    @property
    def base(self):
        return self._base
