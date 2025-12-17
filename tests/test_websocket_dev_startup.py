from pathlib import Path


def test_startup_simple_uses_asgi_for_websockets():
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "startup-simple.sh").read_text(encoding="utf-8")

    # WebSockets require an ASGI server (WSGI gunicorn cannot upgrade connections).
    assert "uvicorn.workers.UvicornWorker" in script
    assert "hood_united.asgi:application" in script

