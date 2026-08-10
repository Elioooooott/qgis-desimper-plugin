BEGIN;

-- TABLES

-- liste_contextes
INSERT INTO desimper.liste_contextes (code, libelle, description, type_valeur, nom_schema, nom_table) VALUES
    ('BAI', 'Baignade', 'Ceci est la description de la baignade', 'integer', 'desimper', 'contexte_baignade')
;

-- communes
INSERT INTO desimper.communes (code_insee, libelle, geom) VALUES
    ('13001', 'Commune de test', ST_Multi(ST_MakeEnvelope(-1000, -1000, 60000, 60000, 2154)))
;

-- projets
INSERT INTO desimper.projets (id, libelle, geom) VALUES
    -- intersects the contexts 1 and 4 of the temporary context table
    (1, 'Projet avec contextes', ST_Multi(ST_GeomFromText('POLYGON((0 0, 0 100, 100 100, 100 0, 0 0))', 2154))),
    -- far away from every context
    (2, 'Projet sans contexte', ST_Multi(ST_GeomFromText('POLYGON((50000 50000, 50000 50100, 50100 50100, 50100 50000, 50000 50000))', 2154)))
;

-- temporary_context_table
DROP TABLE IF EXISTS desimper.test_temp_context_table;
CREATE TABLE desimper.test_temp_context_table (
    id integer PRIMARY KEY,
    label text,
    value integer,
    geom geometry(Polygon, 2154)
);
INSERT INTO desimper.test_temp_context_table (id, label, value, geom) VALUES
    (1, 'Pas de site de baignade', 0, ST_GeomFromText('POLYGON((-10 -10, -10 50, 50 50, 50 -10, -10 -10))', 2154)), -- intersect project 1
    (2, 'Pas de site de baignade', 0, ST_GeomFromText('POLYGON((0 0, 0 -50, -50 -50, -50 0, 0 0))', 2154)), -- 1 point in common with project 1
    (3, 'Site de baignade en aval', 1, ST_GeomFromText('POLYGON((100 0, 100 100, 200 100, 200 0, 100 0))', 2154)), -- 1 line in common with project 1
    (4, 'Site de baignade en aval', 1, ST_Segmentize(ST_GeomFromText('POLYGON((-100 -100, -100 20000, 200 20000, 200 -100, -100 -100))', 2154), 10)), -- overlap project 1 & need to be subdivided
    (5, 'Site de baignade en aval', 1, ST_GeomFromText('POLYGON((1000 1000, 1000 1100, 1100 1100, 1100 1000, 1000 1000))', 2154))-- no intersection with project 1
;

COMMIT;
