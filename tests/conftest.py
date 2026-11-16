"""Shared test settings.

Hypothesis property tests have no time limit. A test result must not
depend on the speed or the load of the host.
"""

from hypothesis import settings

settings.register_profile("phoenix", deadline=None)
settings.load_profile("phoenix")
