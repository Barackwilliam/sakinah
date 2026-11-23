"""Tests are written against the English texts, so they run with the site in English unless a test asks otherwise
(override_settings(LANGUAGE_CODE="sw") or SITE_LANGUAGE="sw")."""
from django.conf import settings
from django.test.runner import DiscoverRunner


class Runner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        settings.SITE_LANGUAGE = ""
