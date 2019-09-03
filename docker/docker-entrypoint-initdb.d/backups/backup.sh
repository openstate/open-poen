#!/bin/bash

## Backup Postgres
DB_NAME=`cat /run/secrets/db_name`
DB_USER=`cat /run/secrets/db_user`
pg_dump -U $DB_USER $DB_NAME | gzip > latest-postgresdump-daily.sql.gz 
cp -p latest-postgresdump-daily.sql.gz `(date +%A)`-postgresdump-daily.sql.gz
