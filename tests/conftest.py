"""
Pytest configuration ve fixtures.
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path

# Test için geçici veritabanı
@pytest.fixture
def temp_db():
    """Geçici veritabanı oluşturur."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_cemil_bot.db")
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_knowledge_base():
    """Geçici knowledge base klasörü oluşturur."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Test için mock environment variables."""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("ADMIN_CHANNEL_ID", "C123456")
    monkeypatch.setenv("SLACK_STARTUP_CHANNEL", "C123456")
