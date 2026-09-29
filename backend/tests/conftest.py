"""Test setup for the AI Specialist flow.

Runs against a separate PostgreSQL database (`lri_test`) created next to the
configured one, so the local development data is never touched. The fake LLM
is forced on and the OpenAI key is forced empty: these tests never call OpenAI.

Run inside the backend container:
    docker compose exec backend python -m pytest tests -q
"""

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

TEST_DB_NAME = 'lri_test'
BACKEND_DIR = Path(__file__).resolve().parents[1]

_base_url = os.environ.get('DATABASE_URL', 'postgresql://lri:lri@db:5432/lri')
_parts = urlsplit(_base_url)
if _parts.path.lstrip('/') == TEST_DB_NAME:
    raise RuntimeError('DATABASE_URL must point to the development database, not the test database')
TEST_DATABASE_URL = urlunsplit(_parts._replace(path=f'/{TEST_DB_NAME}'))

# Must happen before any `app` import: settings are read at import time.
os.environ['DATABASE_URL'] = TEST_DATABASE_URL
os.environ['LLM_MOCK'] = 'true'
os.environ['OPENAI_API_KEY'] = ''


def _recreate_test_database() -> None:
    from sqlalchemy import create_engine, text

    admin_engine = create_engine(_base_url, isolation_level='AUTOCOMMIT')
    with admin_engine.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE {TEST_DB_NAME}'))
    admin_engine.dispose()


@pytest.fixture(scope='session', autouse=True)
def test_database():
    from alembic import command
    from alembic.config import Config

    _recreate_test_database()
    alembic_config = Config(str(BACKEND_DIR / 'alembic.ini'))
    alembic_config.set_main_option('script_location', str(BACKEND_DIR / 'alembic'))
    command.upgrade(alembic_config, 'head')

    from app.seed import seed

    seed()
    yield


@pytest.fixture(scope='session')
def client(test_database):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope='session')
def auth_headers(client):
    from app.seed import DEFAULT_USER_EMAIL, DEFAULT_USER_PASSWORD

    response = client.post('/auth/login', json={'email': DEFAULT_USER_EMAIL, 'password': DEFAULT_USER_PASSWORD})
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def db_session():
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        yield session
