class _FakeEncoder:
    def encode(self, text):
        return [0] * len(text)

def encoding_for_model(_model):
    return _FakeEncoder()
