#!/bin/bash
DBNAME=$(python -c 'from django.conf import settings; print settings.DATABASE_NAME')
django-admin.py dbshell <<EOF
	drop database ${DBNAME};
	create database ${DBNAME};
EOF
django-admin.py syncdb --noinput
django-admin.py shell --plain >> /dev/null <<EOF
from inyoka.portal.user import User
User(username='Anonymous', password='').save()
u = User.objects.register_user('admin', 'admin@example.org', 'default', False)
u.is_manager = True
u.save()
EOF
echo "Created superuser 'admin:default'"

# make sure that the xapian database is recreated
rm -rf $(python -c 'from django.conf import settings; print "\"%s\"" % settings.XAPIAN_DATABASE')
python -c 'import xapian; from django.conf import settings; xapian.WritableDatabase(settings.XAPIAN_DATABASE, xapian.DB_CREATE_OR_OPEN)' && echo "Created xapian database"

# create the media folders
rm -Rf ./inyoka/media
mkdir ./inyoka/media
mkdir ./inyoka/media/portal
mkdir ./inyoka/media/portal/avatars
mkdir ./inyoka/media/forum
mkdir ./inyoka/media/forum/attachments
mkdir ./inyoka/media/planet
mkdir ./inyoka/media/planet/icons
mkdir ./inyoka/media/wiki
mkdir ./inyoka/media/wiki/attachments
echo "Created media directories"

# XXX: why are we converting data in the reset script?
#python inyoka/scripts/converter/create_templates.py
#echo "Created wiki templates"
