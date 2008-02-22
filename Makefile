#
# Inyoka Makefile
# ~~~~~~~~~~~~~~~
#
# Shortcuts for various tasks.
#
# :copyright: 2007 by Armin Ronacher, Christopher Grebs.
# :license: GNU GPL.
#

# remove --introspect-only once this bug is fixed:
# http://sourceforge.net/tracker/index.php?func=detail&aid=1817965&group_id=32455&atid=405618
EPYDOC=epydoc --name=Inyoka --url=http://inyoka.ubuntuusers.de/ --docformat=restructuredtext --debug --introspect-only -o apidoc

test:
	@(cd tests; py.test $(TESTS))

doc:
	@(${EPYDOC} --no-frames --html --css extra/epydoc.css -o apidoc inyoka)

pdfdoc:
	@(${EPYDOC} --pdf -o apidoc inyoka)

reindent:
	@extra/reindent.py -r -B .

reset:
	@(sh reset.sh)

test_data:
	@(sh make_test_data.sh)

convert:
	@(python inyoka/scripts/converter/converter.py)

server:
	@django-admin.py runserver 0.0.0.0:8080

wserver:
	@(python django-run-debugged.py)

profiled:
	@(python inyoka/scripts/start_profiled.py)

shell:
	@django-admin.py shell

mysql:
	@mysql -uroot ubuntuusers

clean-files:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '*.orig' -exec rm -f {} +
