from utils.llm import generate_notes as _generate_notes
from utils.memory import get_cached_notes, save_notes_to_cache

# Bump this whenever the notes prompt/format changes materially — it's
# folded into the cache key so students automatically get freshly
# regenerated (deeper) notes instead of an old, shallower cached version,
# without needing a DB migration.
NOTES_VERSION = "v2-deep"


def get_notes(subject, topic):
    """
    Returns deep AI-generated notes for a subject/topic, using a cache so
    the same topic isn't regenerated (and re-billed against your Groq
    quota) every time a student opens it.
    """
    cache_key = f"{topic}::{NOTES_VERSION}"

    cached = get_cached_notes(subject, cache_key)
    if cached:
        return cached

    content = _generate_notes(subject, topic)
    save_notes_to_cache(subject, cache_key, content)
    return content