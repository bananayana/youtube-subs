#!/bin/sh

# wait for PSQL server to start
sleep 20

# migrate db, so we have the latest db schema
python manage.py migrate

#gunicorn extension.wsgi:application -w 5 -b :8000
python manage.py runserver 0.0.0.0:8000 # --noreload
