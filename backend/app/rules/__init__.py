"""Deterministic Python rule validators (no LLMs).

Run *after* the LLM proposes a count. A hard-rule violation rejects the count
before it reaches the user; soft-rule (heuristic) failures lower the
compliance score but do not reject.
"""
