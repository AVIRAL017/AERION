"""
AERION — Backend Configuration Unit Tests
Tests typed settings, environment modes, production validation rules, and secret protection.
"""

import os
import unittest
from unittest.mock import patch
from pydantic import SecretStr, ValidationError

from app.core.config import AERIONSettings, get_settings


class TestConfiguration(unittest.TestCase):

    def test_default_development_settings(self):
        settings = AERIONSettings()
        self.assertEqual(settings.ENVIRONMENT, "development")
        self.assertFalse(settings.DEBUG)
        self.assertEqual(settings.API_VERSION, "v1")
        self.assertIn("http://localhost:3000", settings.ALLOWED_ORIGINS)
        self.assertTrue(settings.LAZY_LOAD_MODELS)
        self.assertTrue(settings.RATE_LIMIT_ENABLED)

    def test_allowed_origins_string_parsing(self):
        settings = AERIONSettings(ALLOWED_ORIGINS="https://app.aerion.org, https://admin.aerion.org")
        self.assertEqual(settings.ALLOWED_ORIGINS, ["https://app.aerion.org", "https://admin.aerion.org"])

    def test_production_mode_valid(self):
        settings = AERIONSettings(
            ENVIRONMENT="production",
            DEBUG=False,
            ALLOWED_ORIGINS=["https://dashboard.aerion.org"],
        )
        self.assertEqual(settings.ENVIRONMENT, "production")
        self.assertFalse(settings.DEBUG)
        self.assertEqual(settings.ALLOWED_ORIGINS, ["https://dashboard.aerion.org"])

    def test_production_mode_fails_if_debug_true(self):
        with self.assertRaises(ValueError) as ctx:
            AERIONSettings(
                ENVIRONMENT="production",
                DEBUG=True,
                ALLOWED_ORIGINS=["https://dashboard.aerion.org"],
            )
        self.assertIn("DEBUG cannot be enabled in production", str(ctx.exception))

    def test_production_mode_fails_if_wildcard_cors(self):
        with self.assertRaises(ValueError) as ctx:
            AERIONSettings(
                ENVIRONMENT="production",
                DEBUG=False,
                ALLOWED_ORIGINS=["*"],
            )
        self.assertIn("Wildcard origin '*' is strictly prohibited", str(ctx.exception))

    def test_production_mode_fails_if_empty_origins(self):
        with self.assertRaises(ValueError) as ctx:
            AERIONSettings(
                ENVIRONMENT="production",
                DEBUG=False,
                ALLOWED_ORIGINS=[],
            )
        self.assertIn("ALLOWED_ORIGINS must contain explicit origin URLs", str(ctx.exception))

    def test_secret_str_masking(self):
        settings = AERIONSettings(
            MISTRAL_API_KEY=SecretStr("super-secret-key-12345"),
        )
        self.assertIsNotNone(settings.MISTRAL_API_KEY)
        self.assertNotIn("super-secret-key-12345", str(settings.MISTRAL_API_KEY))
        self.assertNotIn("super-secret-key-12345", repr(settings))
        self.assertEqual(settings.MISTRAL_API_KEY.get_secret_value(), "super-secret-key-12345")

    def test_get_settings_caching(self):
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        self.assertIs(s1, s2)
        get_settings.cache_clear()

    def test_models_dir_removed_from_settings(self):
        settings = AERIONSettings()
        self.assertFalse(hasattr(settings, "MODELS_DIR"))

    def test_thresholds_not_configurable_in_settings(self):
        settings = AERIONSettings()
        self.assertFalse(hasattr(settings, "CONFIDENCE_THRESHOLD"))
        self.assertFalse(hasattr(settings, "IOU_THRESHOLD"))
        self.assertFalse(hasattr(settings, "DAMAGE_THRESHOLD"))

    def test_environment_threshold_overrides_ignored_by_settings(self):
        # Settings should not accept or expose threshold overrides
        with patch.dict(os.environ, {
            "CONFIDENCE_THRESHOLD": "0.10",
            "IOU_THRESHOLD": "0.90",
            "DAMAGE_THRESHOLD": "0.20",
            "MODELS_DIR": "/custom/models",
        }):
            settings = AERIONSettings()
            self.assertFalse(hasattr(settings, "CONFIDENCE_THRESHOLD"))
            self.assertFalse(hasattr(settings, "IOU_THRESHOLD"))
            self.assertFalse(hasattr(settings, "DAMAGE_THRESHOLD"))
            self.assertFalse(hasattr(settings, "MODELS_DIR"))


if __name__ == "__main__":
    unittest.main()
