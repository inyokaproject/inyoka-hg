#!/bin/bash
echo "Creating basic database tables..."
DBNAME=$(python -c 'from django.conf import settings; print settings.DATABASE_NAME')
django-admin.py dbshell <<EOF
	drop database ${DBNAME};
	create database ${DBNAME};
EOF
# create the media folders
rm -Rf ./inyoka/media
mkdir ./inyoka/media
mkdir ./inyoka/media/forum
mkdir ./inyoka/media/forum/attachments
mkdir ./inyoka/media/forum/attachments/temp
mkdir ./inyoka/media/forum/thumbnails
mkdir ./inyoka/media/planet
mkdir ./inyoka/media/planet/icons
mkdir ./inyoka/media/wiki
mkdir ./inyoka/media/wiki/attachments
mkdir ./inyoka/media/portal
mkdir ./inyoka/media/portal/avatars
mkdir ./inyoka/media/portal/member_icons
echo "Created media directories"

python -c 'from inyoka.conf import settings;settings.DEBUG = True;from inyoka.utils.migrations import Migrations;from inyoka.migrations import MIGRATIONS;migrations = Migrations(MIGRATIONS);migrations.upgrade()'
echo "finished basic database creation\n"
echo "Create admin user"
python manage-inyoka.py create_superuser

# make sure that the xapian database is recreated
rm -rf $(python -c 'from django.conf import settings; print "\"%s\"" % settings.XAPIAN_DATABASE')
python -c 'import xapian; from django.conf import settings; xapian.WritableDatabase(settings.XAPIAN_DATABASE, xapian.DB_CREATE_OR_OPEN)'
echo "Created xapian database"
