import json
import time

from psycopg2 import connect
from psycopg2 import sql as pg_sql
from qgis import processing
from qgis.core import (
    NULL,
    QgsDataSourceUri,
    QgsExpressionContextUtils,
    QgsProcessing,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingOutputNumber,
    QgsProcessingOutputString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterProviderConnection,
    QgsProcessingParameterEnum,
    QgsProcessingParameterField,
    QgsProject,
    QgsProviderConnectionException,
    QgsProviderRegistry,
)

from ..plugin_tools.i18n import tr
from ..plugin_tools.resources import plugin_name_normalized#, srid_value
from .base_algorithm import BaseProcessingAlgorithm
from .tools import fetch_data_from_sql_query, get_connection_name, get_postgis_connection_list


class ImportContextData(BaseProcessingAlgorithm):
    # Parameters
    CONNECTION_NAME = "CONNECTION_NAME"
    TARGET_CONTEXT = "TARGET_CONTEXT"
    OVERRIDE = "OVERRIDE"
    CONTEXT_LAYER = "CONTEXT_LAYER"
    LABEL_FIELD = "LABEL_FIELD"
    VALUE_FIELD = "VALUE_FIELD"
    UNIQUE_ID_FIELD = "UNIQUE_ID_FIELD"

    OUTPUT_STATUS = "OUTPUT_STATUS"
    OUTPUT_STRING = "OUTPUT_STRING"

    def name(self):
        return "import_context_data"

    def displayName(self):
        return tr("Import context data")

    def group(self):
        return tr("Import data to database")

    def groupId(self):
        return f"{plugin_name_normalized()}_data"

    def shortHelpString(self):
        return tr(
            "This algorithm imports data from a context layer to the database "
            "\n"
            "\n"
            "You will need to provide the following parameters:" \
            "\n"
            "* PostgreSQL connection to the database: name of the database " \
            "connection you would like to use for the installation."
            "\n"
            "* Target context: the context to which the data will be imported."
            "\n"
            "* Context layer: the layer from which the data will be imported."
            "\n"
            "* Label field: the field from which the label will be imported."
            "\n"
            "* Value field: the field from which the value will be imported."
            "\n"
            "* Unique ID field: the field from which the unique ID will be imported."
            "\n"
            "\n"
            "Beware ! The target table of the chosen context is dropped and recreated "
            "during the import: all the data it currently contains will be lost. "
            'If the table is not empty, you must check the "Overwrite" checkbox to confirm.'
        )

    def initAlgorithm(self, config):
        project = QgsProject.instance()
        connection_name = get_connection_name(project)
        get_data = QgsExpressionContextUtils.globalScope().variable('desimper_get_database_data')

        # Connection name
        param = QgsProcessingParameterProviderConnection(
            self.CONNECTION_NAME,
            tr("PostgreSQL connection to the database"),
            "postgres",
            defaultValue=connection_name,
            optional=False,
        )
        param.setHelp(tr("The database where the plugin structure will be installed."))
        self.addParameter(param)

        # Context in list_context
        sql = '''
            SELECT code, libelle
            FROM desimper.liste_contextes
            ORDER BY libelle
        '''
        data = []
        if get_data == 'yes' and connection_name in get_postgis_connection_list():
            data, _ = fetch_data_from_sql_query(connection_name, sql)
        self.context_values = [f'{a[1]} - {a[0]}' for a in data]
        param = QgsProcessingParameterEnum(
            self.TARGET_CONTEXT,
            tr('Target context'),
            options=self.context_values,
            optional=False
            )
        param.setHelp(
            tr("The context to which the data will be imported.")
        )
        self.addParameter(param)

        # Override existing data in the target table
        param = QgsProcessingParameterBoolean(
            self.OVERRIDE,
            tr(
                "Overwrite the existing data of the target context table ? "
                "**CAUTION** It will remove all the data currently stored in it !"
            ),
            defaultValue=False,
        )
        param.setHelp(
            tr(
                "The target table of the context is dropped and recreated during the import. "
                "Check this box to confirm that its current data can be deleted."
            )
        )
        self.addParameter(param)

        # Context layer
        param = QgsProcessingParameterFeatureSource(
            self.CONTEXT_LAYER,
            tr("Context layer"),
            [QgsProcessing.SourceType.TypeVectorPolygon],
        )
        param.setHelp(
            tr("The layer from which the data will be imported.")
        )
        self.addParameter(param)

        # label field
        param = QgsProcessingParameterField(
            self.LABEL_FIELD,
            tr('Label field'),
            parentLayerParameterName=self.CONTEXT_LAYER,
            type=QgsProcessingParameterField.String
        )
        param.setHelp(
            tr("The field from which the label will be imported.")
        )
        self.addParameter(param)

        # value field
        param = QgsProcessingParameterField(
            self.VALUE_FIELD,
            tr('Value field'),
            parentLayerParameterName=self.CONTEXT_LAYER,
            type=QgsProcessingParameterField.Numeric
        )
        param.setHelp(
            tr("The field from which the value will be imported.")
        )
        self.addParameter(param)

        # unique id field
        param = QgsProcessingParameterField(
            self.UNIQUE_ID_FIELD,
            tr('Unique id field'),
            parentLayerParameterName=self.CONTEXT_LAYER,
            type=QgsProcessingParameterField.Any
        )
        param.setHelp(
            tr("The field from which the unique ID will be imported.")
        )
        self.addParameter(param)

        # OUTPUTS
        # Add output for status (integer)
        self.addOutput(QgsProcessingOutputNumber(self.OUTPUT_STATUS, tr("Output status")))
        # Add output for message
        self.addOutput(QgsProcessingOutputString(self.OUTPUT_STRING, tr("Output message")))

    def checkParameterValues(self, parameters, context):
        """Check the validity of the parameters before running the algorithm."""
        # Connection name
        connection_name = self.parameterAsConnectionName(parameters, self.CONNECTION_NAME, context)
        if not connection_name:
            return False, tr("No valid database connection provided.")
        metadata = QgsProviderRegistry.instance().providerMetadata("postgres")
        connection = metadata.findConnection(connection_name)
        if not connection:
            return False, tr("Could not create a connection to the database with the given connection name.")
        pg_conn = connect(QgsDataSourceUri(connection.uri()).connectionInfo())

        # Check if schema_name and table name from liste_contextes exist in the database
        success, error, schema_name, table_name = self._is_valid_schema_table(
            parameters, pg_conn, connection_name
        )
        if not success:
            pg_conn.close()
            return False, error

        # The import drops the target table, the user must confirm the loss of its data
        success, error = self._is_override_confirmed(
            parameters, context, schema_name, table_name, pg_conn, connection_name
        )
        if not success:
            pg_conn.close()
            return False, error

        pg_conn.close()
        return True, ""

    def cleanUp(
        self, connection_name: str, temp_schema: str, temp_tables: list[str], feedback: QgsProcessingFeedback
    ) -> None:
        """Clean up the temporary tables after the algorithm has been run."""
        connection = (
            QgsProviderRegistry.instance().providerMetadata("postgres").findConnection(connection_name)
        )
        pg_conn = connect(QgsDataSourceUri(connection.uri()).connectionInfo())
        for temp_table in temp_tables:
            sql = (
                pg_sql.SQL("DROP TABLE IF EXISTS {schema}.{table}")
                .format(
                    schema=pg_sql.Identifier(temp_schema),
                    table=pg_sql.Identifier(temp_table),
                )
                .as_string(pg_conn)
            )
            try:
                connection.executeSql(sql)
                # feedback.pushInfo(tr(f"* Temporary table {temp_table} has been dropped"))
            except QgsProviderConnectionException as e:
                msg = tr("* Failed to drop temporary table")
                msg += f" {temp_table} ({e!s})"
                feedback.pushInfo(msg)
        pg_conn.close()

    def processAlgorithm(self, parameters, context, feedback):
        """Run the algorithm to import data into the database."""
        msg = ""
        status = 1

        # Parameters
        connection_name = self.parameterAsConnectionName(parameters, self.CONNECTION_NAME, context)
        random_time = str(time.time()).replace(".", "")

        # Import context
        feedback.pushInfo("")
        feedback.pushInfo(tr("IMPORT CONTEXT INTO TEMPORARY TABLE"))
        temp_schema = "public"
        temp_table = "temp_context_" + random_time
        processing.run(
            "gdal:importvectorintopostgisdatabaseavailableconnections",
            {
                "DATABASE": connection_name,
                "INPUT": parameters[self.CONTEXT_LAYER],
                "SHAPE_ENCODING": "",
                "GTYPE": None,
                "A_SRS": None,
                "T_SRS": None,
                "S_SRS": None,
                "SCHEMA": temp_schema,
                "TABLE": temp_table,
                "PK": "",
                "PRIMARY_KEY": "",
                "GEOCOLUMN": "geom",
                "DIM": 0,
                "SIMPLIFY": "",
                "SEGMENTIZE": "",
                "SPAT": None,
                "CLIP": False,
                "WHERE": "",
                "GT": "",
                "OVERWRITE": True,
                "APPEND": False,
                "ADDFIELDS": False,
                "LAUNDER": False,
                "INDEX": False,
                "SKIPFAILURES": False,
                "MAKEVALID": True,
                "PROMOTETOMULTI": True,
                "PRECISION": False,
                "OPTIONS": "",
            },
            context=context,
            feedback=feedback,
        )
        feedback.pushInfo(
            tr("* Context layer has been imported into temporary table") + " " + temp_table
        )

        connection = (
            QgsProviderRegistry.instance().providerMetadata("postgres").findConnection(connection_name)
        )
        pg_conn = connect(QgsDataSourceUri(connection.uri()).connectionInfo())
        target_context = self.context_values[parameters[self.TARGET_CONTEXT]]
        code_context = target_context.split("-")[-1].strip()

        # Check that unique ID field is really unique
        feedback.pushInfo("Check that the unique ID field is really unique")
        success, error = self._is_unique_id_field(
            parameters, temp_schema, temp_table, pg_conn, connection_name
        )
        if not success:
            self.cleanUp(connection_name, temp_schema, [temp_table], feedback)
            raise QgsProcessingException(str(error))
        feedback.pushInfo("* The unique ID field is unique")

        # Convert context data from temporary tables to the production schema
        feedback.pushInfo("")
        feedback.pushInfo(
            tr("CONVERT CONTEXT DATA FROM TEMPORARY TABLE TO THE PRODUCTION SCHEMA")
        )

        sql = (
            pg_sql.SQL("""
            SELECT desimper.import_data_from_temporary_tables(
                {temp_schema},
                {temp_table},
                {label_field},
                {value_field},
                {unique_id_field},
                {code_context}
            ) AS result
        """)
            .format(
                temp_schema=pg_sql.Literal(temp_schema),
                temp_table=pg_sql.Literal(temp_table),
                label_field=pg_sql.Literal(parameters[self.LABEL_FIELD].lower()),
                value_field=pg_sql.Literal(parameters[self.VALUE_FIELD].lower()),
                unique_id_field=pg_sql.Literal(parameters[self.UNIQUE_ID_FIELD].lower()),
                code_context=pg_sql.Literal(code_context),
            )
            .as_string(pg_conn)
        )
        pg_conn.close()
        try:
            data = connection.executeSql(sql)
        except QgsProviderConnectionException as e:
            self.cleanUp(connection_name, temp_schema, [temp_table], feedback)
            raise QgsProcessingException(str(e))
        result = None
        for a in data:
            result = a[0] if a else None
        empty_result = {
            "status": "error",
            "message": "No result returned from the database import function.",
            "data": None,
            "edges_count": 0,
            "nodes_count": 0,
            "roads_count": 0,
            "markers_count": 0,
        }
        json_result = json.loads(result) if result else empty_result

        # Check errors
        if json_result.get("status") != "success":
            error_message = tr("An error occurred while importing the data into the database: ")
            error_message += json_result.get("message", "Unknown error")
            if json_result.get("data"):
                error_message += "\n\n" + tr("* Number: ") + str(json_result["data"]["number"])
                error_message += "\n" + tr("* Details: ") + json_result["data"]["details"]

            status = 0
            self.cleanUp(connection_name, temp_schema, [temp_table], feedback)
            raise QgsProcessingException(error_message)

        # End message
        msg = tr("Context layer has been imported successfully into the database.")
        feedback.pushInfo("")
        feedback.pushInfo(msg)
        status = 1

        # clean up temporary tables
        self.cleanUp(connection_name, temp_schema, [temp_table], feedback)

        return {self.OUTPUT_STATUS: status, self.OUTPUT_STRING: msg}


    def _is_valid_schema_table(self, parameters, pg_conn, connection_name):
        """Check if the schema_name and table_name are listed in the context list table.

        Returns the validity, the error message and the target schema and table names.
        """
        target_context = self.context_values[parameters[self.TARGET_CONTEXT]]
        code_context = target_context.split("-")[-1].strip()
        sql = (
            pg_sql.SQL("""
            SELECT nom_schema, nom_table FROM desimper.liste_contextes WHERE code = {code_context}
        """)
            .format(
                code_context=pg_sql.Literal(code_context),
            )
            .as_string(pg_conn)
        )
        data, error = fetch_data_from_sql_query(connection_name, sql)
        if error:
            return False, error, None, None
        if not data:
            return False, tr(
                "The context selected does not exist in the database. "
                "\n"
                "Create it first in the context list table."
                ), None, None
        schema_name, table_name = data[0][0], data[0][1]
        if schema_name == NULL or table_name == NULL:
            return False, tr(
                "The context selected has no schema or table defined in the database."
                "\n"
                "Create it first in the context list table."), None, None

        return True, "", schema_name, table_name

    def _is_override_confirmed(
        self, parameters, context, schema_name, table_name, pg_conn, connection_name
    ):
        """Check the user confirmed the deletion of the data already in the target table."""
        if self.parameterAsBoolean(parameters, self.OVERRIDE, context):
            return True, ""

        count, error = self._count_target_table_rows(
            schema_name, table_name, pg_conn, connection_name
        )
        if error:
            return False, error
        if count:
            msg = tr(
                "The target table of the selected context already contains data. "
                "The import drops and recreates this table: "
                "if you REALLY want to delete its data, check the *Overwrite* checkbox."
            )
            msg += f"\n\n{schema_name}.{table_name} : {count} "
            msg += tr("existing rows")
            return False, msg

        return True, ""

    def _count_target_table_rows(self, schema_name, table_name, pg_conn, connection_name):
        """Return the number of rows stored in the target table, 0 if it does not exist yet."""
        sql = (
            pg_sql.SQL("""
            SELECT count(*)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = {schema_name} AND c.relname = {table_name}
        """)
            .format(
                schema_name=pg_sql.Literal(schema_name),
                table_name=pg_sql.Literal(table_name),
            )
            .as_string(pg_conn)
        )
        data, error = fetch_data_from_sql_query(connection_name, sql)
        if error:
            return 0, error
        if not data or not data[0][0]:
            # The table does not exist yet, it will be created by the import
            return 0, None

        sql = (
            pg_sql.SQL("SELECT count(*) FROM {schema}.{table}")
            .format(
                schema=pg_sql.Identifier(schema_name),
                table=pg_sql.Identifier(table_name),
            )
            .as_string(pg_conn)
        )
        data, error = fetch_data_from_sql_query(connection_name, sql)
        if error:
            return 0, error

        return data[0][0], None

    def _is_unique_id_field(self, parameters, schema, table, pg_conn, connection_name):
        """Check that the unique ID field is really unique."""
        sql = (
            pg_sql.SQL("""
            SELECT COUNT(DISTINCT({unique_id_field})) AS unique, COUNT(*) AS total FROM {schema}.{table}
        """)
            .format(
                unique_id_field=pg_sql.Identifier(parameters[self.UNIQUE_ID_FIELD].lower()),
                schema=pg_sql.Identifier(schema),
                table=pg_sql.Identifier(table),
            )
            .as_string(pg_conn)
        )
        data, error = fetch_data_from_sql_query(connection_name, sql)
        if error:
            return False, error
        if not data:
            return False, tr(
                "The temporary table does not exist in the database. "
                )
        count_id, count_total = data[0][0], data[0][1]
        if count_id != count_total:
            return False, tr(
                "The unique ID field contains non-unique values."
                "\n"
                "Be sure you selected the right field."
                )

        return True, ""
