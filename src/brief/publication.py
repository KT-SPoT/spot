"""Reader copy is separate from collection and Critic diagnostics."""
import re


def publication_text(value):
    text=str(value or '')
    # Omit diagnostic sentences, rather than suggesting that evidence exists.
    parts=re.split(r'(?<=[.!?。])\s+|\n',text)
    return ' '.join(p for p in parts if not re.search(r'미확보|확보하지 못|근거 부족|근거미확보|근거 미확보',p))
