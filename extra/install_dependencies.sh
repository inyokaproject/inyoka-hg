# this installs all the dependencies needed for inyoka
# it should work with Ubuntu Gutsy, anything else has not been tested

cd /opt
sudo su

aptitude install mercurial subversion python-simplejson mysql-server mysql-client python-openid python-xapian

svn co http://code.djangoproject.com/svn/django/trunk/ django
ln -s /opt/django/django /usr/lib/python2.5/site-packages/
ln -s /opt/django/django/bin/django-admin.py /usr/bin/

hg clone http://dev.pocoo.org/hg/jinja-main jinja
ln -s /opt/jinja/jinja /usr/lib/python2.5/site-packages/

wget http://html5lib.googlecode.com/files/html5lib-0.10.zip
unzip html5lib-0.10.zip 
rm html5lib-0.10.zip
cd html5lib-0.10/
python setup.py install
cd ..

hg clone http://dev.pocoo.org/hg/pygments-main pygments
ln -s /opt/pygments/pygments /usr/lib/python2.5/site-packages/
ln -s /opt/pygments/pygmentize /usr/bin/
ln -s /opt/pygments/docs/pygmentize.1 /usr/share/man/man1/

hg clone http://dev.pocoo.org/hg/werkzeug-main werkzeug
ln -s /opt/werkzeug/werkzeug /usr/lib/python2.5/site-packages/

wget http://mesh.dl.sourceforge.net/sourceforge/pytz/pytz-2006p.tar.bz2
tar -xvjf pytz-2006p.tar.bz2
cd pytz-2006p/
python setup.py install
cd ..

