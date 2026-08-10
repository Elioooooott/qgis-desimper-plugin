"""Tests the algorithms & the SQL functions of the plugin."""

from decimal import Decimal
from typing import Any

import psycopg

from qgis import processing
from qgis.core import QgsVectorLayer

from desimper.plugin_tools.feedback import LoggerProcessingFeedBack
from desimper.processing.provider import Provider


def test_import_context(
    connected_database: None,
    initialized_database: psycopg.Connection,
    context_layer: QgsVectorLayer,
    processing_provider: Provider,
    imported_context: dict[str, Any],
):
    """Import a context layer into the target table of an existing context."""
    # Algorithm is working
    assert imported_context["OUTPUT_STATUS"] == 1
    assert imported_context["OUTPUT_STRING"] == (
        "Context layer has been imported successfully into the database."
    )

    # Data has been imported
    cursor = initialized_database.cursor()
    cursor.execute(
        """
        SELECT unique_object_id, fk_code_liste_contextes, libelle, valeur
        FROM desimper.contexte_baignade
        WHERE fk_code_liste_contextes = 'BAI'
        ORDER BY unique_object_id
        LIMIT 1
        """
    )

    records = cursor.fetchall()
    result = records[0]
    assert result[0] == "1"
    assert result[1] == "BAI"
    assert result[2] == "Pas de site de baignade"
    assert result[3] == "0"

    # View has been created
    cursor.execute(
        """
        SELECT COUNT(*) FROM desimper.v_contexte_baignade
        """
    )
    records = cursor.fetchall()
    result = records[0][0]
    assert result > 0

    # Overide is working
    params = {
        "CONNECTION_NAME": "test",
        "TARGET_CONTEXT": 0,  # 0 = Baignade
        "OVERRIDE": True,
        "CONTEXT_LAYER": context_layer,
        "LABEL_FIELD": "label",
        "VALUE_FIELD": "value",
        "UNIQUE_ID_FIELD": "id",
    }
    feedback = LoggerProcessingFeedBack()
    alg = f"{processing_provider.id()}:import_context_data"
    processing_output = processing.run(alg, params, feedback=feedback)
    assert processing_output["OUTPUT_STATUS"] == 1

    cursor.execute(
        """
        SELECT COUNT(*) FROM desimper.contexte_baignade
        """
    )
    records = cursor.fetchall()
    result = records[0][0]
    assert result == 6  # 5 features, but 1 is subdivised


def test_fill_contextes_projets(
    initialized_database: psycopg.Connection,
    imported_context: dict[str, Any],
):
    """Fill the contextes_projets table with the contexts intersecting a project."""
    assert imported_context["OUTPUT_STATUS"] == 1

    cursor = initialized_database.cursor()

    # Unknown project is rejected
    cursor.execute("SELECT desimper.fill_contextes_projets(-1)")
    record = cursor.fetchone()
    assert record is not None
    result = record[0]
    assert result["status"] == "error"
    assert result["message"] == "Le projet passé en paramètre n'existe pas"

    # The contexts intersecting the project are inserted
    cursor.execute("SELECT desimper.fill_contextes_projets(1)")
    record = cursor.fetchone()
    assert record is not None
    result = record[0]
    assert result["status"] == "success"
    assert result["contexts_intersected"] == 1
    assert result["rows_inserted"] > 0

    # The right contexts intersecting the project are inserted
    cursor.execute("""
        SELECT id, fk_id_projet, surface_m, code_contexte, id_objet_contexte
        FROM desimper.contextes_projets
        ORDER BY id
    """)
    assert cursor.fetchone() == (1, 1, Decimal("2500.00"), "BAI", 1)
    assert cursor.fetchone() == (2, 1, Decimal("10000.00"), "BAI", 4)

    # Running the function again does not duplicate the rows
    cursor.execute("SELECT desimper.fill_contextes_projets(1)")
    record = cursor.fetchone()
    assert record is not None
    assert record[0]["rows_inserted"] == 2

    # A project without any intersecting context inserts nothing
    cursor.execute("SELECT desimper.fill_contextes_projets(2)")
    record = cursor.fetchone()
    assert record is not None
    result = record[0]
    assert result["status"] == "success"
    assert result["rows_inserted"] == 0
    assert result["contexts_intersected"] == 0
