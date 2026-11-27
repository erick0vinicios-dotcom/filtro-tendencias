import re


def _pattern(words):
    cleaned = sorted({word.lower().strip() for word in words if word.strip()}, key=len, reverse=True)
    if not cleaned:
        return None
    alternatives = "|".join(re.escape(word) for word in cleaned)
    return re.compile(rf"(?<![a-z0-9])({alternatives})(?![a-z0-9])")


def build_matcher(settings):
    keywords = _pattern(settings.get("keywords", []))
    excluded = _pattern(settings.get("exclude_keywords", []))
    topics = {topic.lower() for topic in settings.get("topics", [])}

    def match(item):
        text = f"{item['name']} {item['description']}".lower()
        if excluded and excluded.search(text):
            return []
        found = {f"#{topic}" for topic in item.get("topics", []) if topic.lower() in topics}
        if keywords:
            found.update(hit.group(1) for hit in keywords.finditer(text))
        return sorted(found)

    return match
