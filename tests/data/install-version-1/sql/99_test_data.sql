-- BEGIN;

-- -- TABLES

-- -- liste_contextes
-- INSERT INTO desimper.liste_contextes (code, libelle, description, type_valeur, nom_schema, nom_table) VALUES
--     ('BAI', 'Baignade', 'Ceci est la description de la baignade', 'integer', 'desimper', 'contexte_baignade')
-- ;

-- -- temporary_context_table
-- DROP TABLE IF EXISTS desimper.test_temp_context_table;
-- CREATE TABLE desimper.test_temp_context_table (
--     id integer PRIMARY KEY,
--     label text,
--     value integer,
--     geom geometry(Polygon, 2154)
-- );
-- INSERT INTO desimper.test_temp_context_table (id, label, value, geom) VALUES
--     -- theses polygons don't need to be subdivided
--     (1, 'Pas de site de baignade', 0, ST_GeomFromText('POLYGON((0 0, 0 100, 100 100, 100 0, 0 0))', 2154)),
--     (2, 'Pas de site de baignade', 0, ST_GeomFromText('POLYGON((0 0, 0 -50, -50 -50, -50 0, 0 0))', 2154)),
--     (3, 'Site de baignade en aval', 1, ST_GeomFromText('POLYGON((200 200, 200 300, 300 300, 300 200, 200 200))', 2154)),
--     -- this polygon needs to be subdivided
--     (4, 'Site de baignade en aval', 1, ST_Segmentize(ST_MakeEnvelope(0, 0, 10000, 10000, 2154), 10))
-- ;

-- COMMIT;
