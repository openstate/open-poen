# Open Poen
Publish transactions of government subsidized projects


## Requirements
[Docker Compose](https://docs.docker.com/compose/install/)

## Run
- Clone or download this project from GitHub
- In the `docker` directory create the files `secrets-db-name.txt`, `secrets-db-user.txt` and `secrets-db-password.txt` and add the database name, user and password (either new values if starting from scratch or existing if importing a database) on the first line of the corresponding file
- Copy `config.py.example` to `config.py` and edit it
   - Create a SECRET_KEY as per the instructions in the file
   - Specify email related information in order for the application to send emails
- Production
   - Make sure to copy the latest database backup from `docker/docker-entrypoint-initdb.d/backups` to `docker/docker-entrypoint-initdb.d` if you want to import it
   - `cd docker`
   - `sudo docker-compose up -d`
   - Compile the assets, see the section below
   - Set up daily backups for the database
      - To run manually use `sudo docker exec poen_db_1 ./backup.sh`
      - To set a daily cronjob at 03:26
         - `sudo crontab -e` and add the following line
         - `26 3 * * * sudo docker exec poen_db_1 ./backup.sh`
      - The resulting SQL backup files are saved in `docker/docker-entrypoint-initdb.d/backups`
- Development; Flask debug will be turned on which automatically reloads any changes made to Flask files so you don't have to restart the whole application manually
   - Make sure to copy the latest database backup from `docker/docker-entrypoint-initdb.d/backups` to `docker/docker-entrypoint-initdb.d` if you want to import it
   - `cd docker`
   - `docker-compose -f docker-compose.yml -f docker-compose-dev.yml up -d`
   - Compile the assets, see the section below
   - Retrieve the IP address of the nginx container `sudo docker inspect --format='{{.NetworkSettings.Networks.poen_internal.IPAddress}}' poen_nginx_1` and add it to your hosts file `/etc/hosts`: `<IP_address> openpoen.nl`
   - You can now visit http://openpoen.nl in your browser
- Useful commands
   - Run the tests: `sudo docker exec -it poen_app_1 nosetests`
   - Remove and rebuild everything (NOTE: this also removes the database volume containing all transaction data (this is required if you want to load the .sql files from `docker/docker-entrypoint-initdb.d` again))
      - Production: `sudo docker-compose down --rmi all && sudo docker volume rm poen_db && sudo docker-compose up -d`
      - Development: `sudo docker-compose -f docker-compose.yml -f docker-compose-dev.yml down --rmi all && sudo docker volume rm poen_db && sudo docker-compose -f docker-compose.yml -f docker-compose-dev.yml up -d`
   - Reload Nginx: `sudo docker exec poen_nginx_1 nginx -s reload`
   - Reload uWSGI (only for production as development environment doesn't use uWSGI and automatically reloads changes): `touch uwsgi-touch-reload`

## Compile assets
- Install all packages (only need to run once after installation or when you change packages): `sudo docker exec poen_node_1 yarn`

Production
- Build CSS/JS to static/dist directory: `sudo docker exec poen_node_1 yarn prod`

Development
- Build CSS/JS to static/dist directory (with map files): `sudo docker exec poen_node_1 yarn dev`
- Automatically build CSS/JS when a file changes (simply refresh the page in your browser after a change): `sudo docker exec poen_node_1 yarn watch`

## CLI
To access the CLI of the app run `sudo docker exec -it poen_app_1 bash` and run for example `flask` and `flask database` to see the available commands. Here are some CLI commands:

### Database migration commands

Use these after the database is in production and you need to change the database model.

- After changing the model: `flask db migrate -m <message>`
- Apply the new migration to the database: `flask db upgrade`

### Bunq commands

- `flask bunq get-recent-payments` gets the recents payments from the Bunq API

## To enter the database
   - `sudo docker exec -it poen_db_1 psql -U <DB_USER> <DB_NAME>` retrieve database user and name from `docker/secrets-db-user.txt` and `docker/secrets-db-name.txt`
