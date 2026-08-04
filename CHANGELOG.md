# Changelog

## Unreleased

## 0.2.0 - 2026-08-04

### Added

* Import context data from an external layer
    * New processing algorithm `import_context_data`
    * New SQL function `import_data_from_temporary_tables()`, which creates the
      target table and view on demand

### Changed

* Database schema version 2
    * `liste_contextes.nom_schema` and `nom_table` are now `VARCHAR(50)` and `NOT NULL`
    * `liste_contextes.type_geom` has been dropped
* Update the plugin icon
* Build SQL queries with `psycopg2.sql` composition instead of f-strings,
  preventing SQL injection

### Removed

* The `contexte_baignade` and `contexte_mouvement_terrain` tables are no longer
  part of the default structure.

### Fixed

* Fix documentation links


## 0.1.0 - 2026-06-10

* First version of the plugin