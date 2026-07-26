"""Small, dependency-free helpers shared across layers.

Centralizing ID generation and clock access here (rather than calling
``uuid4()`` / ``datetime.now()`` inline everywhere) gives the platform a
single point of change if the ID scheme or time source ever needs to
change, and makes the clock mockable in tests.
"""
