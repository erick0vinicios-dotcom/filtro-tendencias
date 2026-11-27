import re
from collections import defaultdict

SECOND_LEVEL_LABELS = {"co", "com", "org", "net", "ac", "gov", "edu"}
BY_SUFFIX = re.compile(r"\s+by\s+.+$")
FILE_SUFFIX = re.compile(r"\.(py|js|ts|rs|go|sh|app|ai|io|dev|com|so|sh)$")
VERSION = re.compile(r"\bv?\d+(\.\d+)*\b")
NON_ALNUM = re.compile(r"[^a-z0-9]")


def normalize_name(name):
    text = BY_SUFFIX.sub("", (name or "").lower().strip())
    text = FILE_SUFFIX.sub("", text)
    text = VERSION.sub(" ", text)
    return NON_ALNUM.sub("", text)


def key_label(key, hosting_suffixes):
    host, _, path = key.partition("/")
    if path:
        return path.rsplit("/", 1)[-1]
    for suffix in hosting_suffixes:
        if host.endswith(f".{suffix}"):
            return host[: -len(suffix) - 1].rsplit(".", 1)[-1]
    labels = host.split(".")
    if len(labels) >= 3 and labels[-2] in SECOND_LEVEL_LABELS:
        return labels[-3]
    return labels[-2] if len(labels) >= 2 else labels[0]


def domain_keys(item):
    return [key for key in [item.get("key"), *item.get("alt_keys", [])] if key]


def name_keys(item, settings):
    stopwords = set(settings.get("name_stopwords", []))
    minimum = settings.get("name_match_min_length", 5)
    hosting = settings.get("hosting_suffixes", [])
    candidates = {normalize_name(item["name"])}
    candidates.update(normalize_name(key_label(key, hosting)) for key in domain_keys(item))
    return [f"name:{name}" for name in candidates if len(name) >= minimum and name not in stopwords]


class _DisjointSet:
    def __init__(self, size):
        self.parent = list(range(size))

    def find(self, index):
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def union(self, first, second):
        self.parent[self.find(first)] = self.find(second)

    def link(self, keys_per_item):
        owner = {}
        for index, keys in enumerate(keys_per_item):
            for key in keys:
                if key in owner:
                    self.union(index, owner[key])
                else:
                    owner[key] = index


def unify(items, settings):
    groups = _DisjointSet(len(items))
    groups.link([domain_keys(item) for item in items])
    domain_roots = [groups.find(index) for index in range(len(items))]
    groups.link([name_keys(item, settings) for item in items])

    members = defaultdict(list)
    for index in range(len(items)):
        members[groups.find(index)].append(index)

    return [
        {
            "members": [items[index] for index in indexes],
            "matched_by_name": len({domain_roots[index] for index in indexes}) > 1,
        }
        for indexes in members.values()
    ]
