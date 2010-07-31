#
# Inyoka Makefile
# ~~~~~~~~~~~~~~~
#
# Shortcuts for various tasks.
#
# :copyright: 2007-2008 by Armin Ronacher, Christopher Grebs.
# :license: GNU GPL.

.PHONY: test reindent migrate test_data convert server profiled \
	shell mysql clean-files

test:
	@(python run_tests.py)

reindent:
	@extra/reindent.py -r -B .

syncdb:
	@(python manage-django.py syncdb)

migrate:
	@(python manage-django.py migrate)

test_data:
	@(python make_testdata.py)

convert:
	@(python inyoka/scripts/converter/converter.py)

server_cherrypy:
	@(python manage-inyoka.py runcp)

server:
	@(python manage-inyoka.py runserver)

profiled:
	@(python manage-inyoka.py profiled)

shell:
	@(python manage-inyoka.py shell)

mysql:
	@(python manage-inyoka.py mysql)

clean-files:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '*.orig' -exec rm -f {} +
	find . -name '*.orig.*' -exec rm -f {} +
	find . -name '*.py.fej' -exec rm -f {} +
