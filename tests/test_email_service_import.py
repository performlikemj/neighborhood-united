import importlib


def test_email_service_imports_cleanly():
    """Module should import without syntax errors so admin autodiscovery works."""
    importlib.invalidate_caches()
    module = importlib.import_module("meals.email_service")

    assert hasattr(module, "generate_user_summary")
