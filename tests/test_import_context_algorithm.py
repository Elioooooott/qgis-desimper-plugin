"""Tests for the import context algorithm."""

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
):
    """Import a context layer into the target table of an existing context."""
    # Algorithm is working
    params = {
        "CONNECTION_NAME": "test",
        "TARGET_CONTEXT": 0, # 0 = Baignade
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
    assert processing_output["OUTPUT_STRING"] == (
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
    assert result[0] == '1'
    assert result[1] == 'BAI'
    assert result[2] == 'Pas de site de baignade'
    assert result[3] == '0'

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
        "TARGET_CONTEXT": 0, # 0 = Baignade
        "OVERRIDE": True,
        "CONTEXT_LAYER": context_layer,
        "LABEL_FIELD": "label",
        "VALUE_FIELD": "value",
        "UNIQUE_ID_FIELD": "id",
    }
    processing_output = processing.run(alg, params, feedback=feedback)
    assert processing_output["OUTPUT_STATUS"] == 1

    cursor.execute(
        """
        SELECT COUNT(*) FROM desimper.contexte_baignade
        """
    )
    records = cursor.fetchall()
    result = records[0][0]
    assert result == 5
