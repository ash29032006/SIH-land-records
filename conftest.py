"""Repo-root conftest: puts the repo on sys.path and calms hypothesis timing."""

from hypothesis import HealthCheck, settings

settings.register_profile(
    "kavach",
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("kavach")
