"""Small BERT uncased WordPiece tokenizer for the pinned MiniLM vocabulary.

Keeps CPU serving independent of remote-model download libraries. Parity tests
compare it against the upstream Rust tokenizer on all contracts and demo text.
"""
import unicodedata


def punctuation(char):
    code = ord(char)
    return 33 <= code <= 47 or 58 <= code <= 64 or 91 <= code <= 96 or 123 <= code <= 126 or unicodedata.category(char).startswith("P")


def chinese(char):
    code = ord(char)
    return any(lo <= code <= hi for lo, hi in ((0x4E00,0x9FFF),(0x3400,0x4DBF),(0x20000,0x2A6DF),(0x2A700,0x2B73F),(0x2B740,0x2B81F),(0x2B820,0x2CEAF),(0xF900,0xFAFF),(0x2F800,0x2FA1F)))


class WordPiece:
    def __init__(self, vocabulary):
        self.vocab = vocabulary

    def encode(self, text, max_length=256):
        clean = []
        for char in text:
            if char in "\t\n\r" or char.isspace():
                clean.append(" ")
            elif ord(char) not in (0, 0xFFFD) and not unicodedata.category(char).startswith("C"):
                clean.extend((" ",char," ")) if chinese(char) else clean.append(char)
        normalized = unicodedata.normalize("NFD", "".join(clean).lower())
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        separated = "".join(" "+char+" " if punctuation(char) else char for char in normalized)
        pieces = []
        for word in separated.split():
            if len(word) > 100:
                pieces.append(self.vocab["[UNK]"])
                continue
            start, current = 0, []
            while start < len(word):
                end = len(word)
                while end > start:
                    piece = word[start:end] if start == 0 else "##"+word[start:end]
                    if piece in self.vocab:
                        break
                    end -= 1
                if end == start:
                    current = [self.vocab["[UNK]"]]
                    break
                current.append(self.vocab[piece])
                start = end
            pieces.extend(current)
        return [self.vocab["[CLS]"]]+pieces[:max_length-2]+[self.vocab["[SEP]"]]
