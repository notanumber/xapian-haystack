import os

from .settings import *

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.messages",
    "django.contrib.contenttypes",
    "haystack",
    "test_haystack.core",
    "test_haystack.xapian_tests",
]

HAYSTACK_CONNECTIONS = {
    "default": {
        "ENGINE": "haystack.backends.xapian_backend.XapianEngine",
        "PATH": os.path.join("tmp", "test_xapian_query"),
        "INCLUDE_SPELLING": True,
    }
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
