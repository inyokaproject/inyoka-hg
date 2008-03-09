#
# Inyoka Makefile
# ~~~~~~~~~~~~~~~
#
# Shortcuts for various tasks.
#
# :copyright: 2007-2008 by Armin Ronacher, Christopher Grebs.
# :license: GNU GPL.
#

# remove --introspect-only once this bug is fixed:
# http://sourceforge.net/tracker/index.php?func=detail&aid=1817965&group_id=32455&atid=405618
EPYDOC=epydoc --name=Inyoka --url=http://inyoka.ubuntuusers.de/ --docformat=restructuredtext --debug --introspect-only -o apidoc

.PHONY: test doc pdfdoc reindent migrate test_data convert server profiled \
	shell mysql clean-files

test:
	@(cd tests; py.test $(TESTS))

doc:
	@(${EPYDOC} --no-frames --html --css extra/epydoc.css -o apidoc inyoka)

pdfdoc:
	@(${EPYDOC} --pdf -o apidoc inyoka)

reindent:
	@extra/reindent.py -r -B .

migrate:
	@(python manage-inyoka.py migrate)

test_data:
	@(sh make_test_data.sh)

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
	@mysql -uroot ubuntuusers

clean-files:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '*.orig' -exec rm -f {} +
