#!/bin/bash
python make_testdata.py
#django-admin.py shell <<EOF
#$(cat make_testdata.py)
#EOF
echo "Created testdata"
