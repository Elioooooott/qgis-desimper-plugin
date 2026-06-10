Initialisation des fichiers SQL lors de la première initialisation du plugin à partir de lizexample-plugin

```bash
# Aller au répertoire
cd .docker

# On doit avoir une base de donnée avec la structure attendue
# Si les tables de nomenclature sont préfixées par glossary_, ok
# Sinon, modifier le script sh pour prendre en compte le nouveau préfixe. Par ex: nomenclature_
sed -i "s/glossary_/nomenclature_/g" export_database_structure_to_SQL.sh

# Exporter les fichiers SQL du schéma du nouveau plugin depuis cette base
# Ex si le service vers la bdd locale s'appelle pg_desimper_service et le schéma desimper
DB_SERVICE=pg_desimper_service
DB_SCHEMA=desimper
./export_database_structure_to_SQL.sh $DB_SERVICE $DB_SCHEMA

# Bug pour le fichier 20 qui s'appelle '20_TABLE|SEQUENCE|DEFAULT.sql' au lieu de 20_TABLE_SEQUENCE_DEFAULT.sql
mv $DB_SCHEMA/20_TABLE\|SEQUENCE\|DEFAULT.sql $DB_SCHEMA/20_TABLE_SEQUENCE_DEFAULT.sql 

# Un nouveau répertoire du nom $DB_SCHEMA a dû être créé 
# remplacer le contenu de PLUGINNAME/install/$DB_SCHEMA/ par son contenu
cd ..
rm desimper/install/sql/desimper/*
cp .docker/desimper/* desimper/install/sql/desimper/
ls -lh desimper/install/sql/desimper/
```

Ensuite, initialiser le dépôt GIT (voir `CREATE_PLUGIN.sh`)

```bash
# remove git
# rm -rf .git
# git init --initial-branch=main
# git add --all
# git commit -m "Initial commit"
# git log
# git remote add hub git@github.com:3liz/"$PLUGIN_GITHUB_REPOSITORY".git

```

Ensuite, créer une nouvelle version de la base pour les modifications ultérieures nécessaires (si besoin)

TODO : dans lizexample, 
* modifier le script ./export_database_structure_to_SQL.sh pour ajouter un 3ème paramètre avec le préfixe des tables de nomenclature
* supprimer le README contenu dans lizexample/install/sql/ et dans le bon README (contribute ?) mettre le contenu ci-dessus 