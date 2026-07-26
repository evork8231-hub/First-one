"""Lead generation implementation.

Turns RuleMatches into scored, reasoned Lead entities. Signal-level
scoring (``estimated_confidence``) and lead-level scoring
(``intent_score``) are computed independently, per the mission's
requirement that the two scoring systems stay separate. Weather signals
are deliberately excluded from a Lead's supporting evidence -- they only
ever scale the resulting scores.
"""
