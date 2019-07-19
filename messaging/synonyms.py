import os
from threading import RLock

from weavelib.exceptions import ObjectAlreadyExists


class SynonymRegistry(object):
    def __init__(self):
        self.synonym_lock = RLock()
        self.synonyms = {}

    def register(self, synonym, target):
        synonym = os.path.join("/synonyms", synonym.lstrip('/'))
        with self.synonym_lock:
            if synonym in self.synonyms:
                raise ObjecObjectAlreadyExists(synonym)

            self.synonyms[synonym] = target
            return synonym

    def translate(self, synonym):
        with self.synonym_lock:
            return self.synonyms.get(synonym, synonym)

