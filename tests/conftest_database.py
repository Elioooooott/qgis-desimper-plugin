"""Base class for tests using a database."""

import os

from pathlib import Path
from typing import Iterator, Optional, Sequence

import psycopg
import pytest

from qgis import processing
from qgis.core import (
    QgsApplication,
    QgsDataSourceUri,
    QgsProviderRegistry,
    QgsVectorLayer,
)

from desimper.plugin_tools import resources
from desimper.plugin_tools.feedback import LoggerProcessingFeedBack
from desimper.processing.provider import Provider
from desimper.processing.tools import provider_id


# Return the latest upgrade version
@pytest.fixture(scope="session")
def db_install_version() -> Optional[int]:
    version = os.getenv("DB_INSTALL_VERSION")
    if version is not None:
        return int(version)
    latest = resources.latest_upgrade()
    print("Latest upgrade", latest)
    return latest[0] if latest else None


# Return the schema defined in environment
@pytest.fixture(scope="session")
def db_schema() -> str:
    return os.getenv("SCHEMA", resources.schema_name())


# Register the processing provider once
@pytest.fixture(scope="session")
def processing_provider() -> Provider:
    """Initialize processing"""

    pr_id = provider_id()

    registry = QgsApplication.processingRegistry()
    provider = registry.providerById(pr_id)

    assert provider is not None
    assert registry.algorithmById(f"{pr_id}:create_database_structure") is not None
    assert registry.algorithmById(f"{pr_id}:upgrade_database_structure") is not None

    return provider


@pytest.fixture(scope="session")
def db_test_sql(data: Path) -> Sequence[Path]:
    """Return the list of sql scripts to run
    when initializing database for tests
    """
    return (data.joinpath("install-version-1", "sql", "99_test_data.sql"),)


# The following is executed  in each test
#
# Initialize (Override existing) and return a db
# connection
@pytest.fixture()
def db_connection() -> Iterator[psycopg.Connection]:
    """Initialize (Override existing) and return a db connection"""
    if os.getenv("CI_ENV", "").lower() == "docker":
        connection = psycopg.connect(
            user="docker", password="docker", host="db", port="5432", dbname="gis", autocommit=True
        )
    else:
        connection = psycopg.connect(
            user="docker", password="docker", host="localhost", port="35432", dbname="gis", autocommit=True
        )
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture()
def initialized_database(
    db_connection: psycopg.Connection,
    processing_provider: Provider,
    db_test_sql: Sequence[Path],
) -> psycopg.Connection:
    """Create a fresh database structure and load test data"""
    params = {
        "CONNECTION_NAME": "test",
        "OVERRIDE": True,
    }
    feedback = LoggerProcessingFeedBack()

    alg = f"{processing_provider.id()}:create_database_structure"
    processing_output = processing.run(alg, params, feedback=feedback)

    assert processing_output["OUTPUT_STATUS"] == 1
    assert processing_output["OUTPUT_VERSION"] == resources.schema_version()

    cursor = db_connection.cursor()
    for sql_file in db_test_sql:
        with Path.open(sql_file, "r") as f:
            cursor.execute(f.read())
    cursor.close()
    db_connection.commit()

    return db_connection


@pytest.fixture()
def connected_database(processing_provider: Provider) -> None:
    """Configure the plugin connection"""
    params = {"CONNECTION_NAME": "test"}
    alg = f"{processing_provider.id()}:configure_plugin"
    processing.run(alg, params)


@pytest.fixture()
def context_layer(initialized_database: psycopg.Connection, db_schema: str) -> QgsVectorLayer:
    """Return the test context layer stored in the database"""
    metadata = QgsProviderRegistry.instance().providerMetadata("postgres")
    connection = metadata.findConnection("test")
    assert connection is not None

    uri = QgsDataSourceUri(connection.uri())
    uri.setDataSource(db_schema, "test_temp_context_table", "geom", "", "id")

    layer = QgsVectorLayer(uri.uri(), "context_layer", "postgres")
    assert layer.isValid(), layer.error().message()

    return layer
