# this installs all the dependencies needed for inyoka
# it should work with Ubuntu Gutsy, anything else has not been tested
# This Script should be run with root previlegs

if [ $(id -u) != "0" ];then
    echo "This script has to be run as root";
    exit;
fi

cd /opt

aptitude install --assume-yes mercurial subversion python-simplejson mysql-server mysql-client python-openid python-tz python-mysqldb python-xapian python-setuptools python-imaging

svn co http://code.djangoproject.com/svn/django/trunk/ django
ln -s /opt/django/django /usr/lib/python2.5/site-packages/
ln -s /opt/django/django/bin/django-admin.py /usr/bin/

#hg clone http://dev.pocoo.org/hg/jinja-main jinja
#ln -s /opt/jinja/jinja /usr/lib/python2.5/site-packages/

hg clone http://dev.pocoo.org/hg/jinja2-main jinja2
ln -s /opt/jinja2/jinja2 /usr/lib/python2.5/site-packages/

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

#svn checkout http://svn.sqlalchemy.org/sqlalchemy/trunk sqlalchemy
#ln -s /opt/sqlalchemy/lib/sqlalchemy /usr/lib/python2.5/site-packages/

wget 'http://prdownloads.sourceforge.net/sqlalchemy/SQLAlchemy-0.4.6.tar.gz?download'
tar -xvf SQLAlchemy-0.4.6.tar.gz
rm SQLAlchemy-0.4.6.tar.gz
mv SQLAlchemy-0.4.6 sqlalchemy
ln -s /opt/sqlalchemy/lib/sqlalchemy /usr/lib/python2.5/site-packages/

svn co http://www.dnspython.org/svn/dnspython/head/ dnspython
ln -s /opt/dnspython/dns /usr/lib/python2.5/site-packages/
