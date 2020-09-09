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
   - Link a main Bunq account to Open Poen (you need to do this in order to link other Bunq accounts to projects using OAuth)
      - Edit `config.py` and add values for `BUNQ_CLIENT_ID` and `BUNQ_CLIENT_SECRET`; you can obtain these from the Bunq app (you need a Bunq bank account) 'Profile > Security & Settings > Developers > OAuth > Show client details' and also make sure to add `https://openpoen.nl/` as redirect URL
   - Make sure to copy the latest database backup from `docker/docker-entrypoint-initdb.d/backups` to `docker/docker-entrypoint-initdb.d` if you want to import it
   - `cd docker`
   - `sudo docker-compose up -d`
   - Compile the assets, see the section below
   - Set up a crawl of all Bunq bank accounts connected to projects to retrieve new payments every minute
      - `sudo crontab -e` and add the following line
      - `* * * * * (sleep 10; sudo docker exec poen_app_1 flask bunq get-new-payments-all)`
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
   - Link a main Bunq account to Open Poen (you need to do this in order to link other Bunq accounts to projects using OAuth); you can use either a Production (actual) Bunq account or a Sandbox Bunq account; Note that you can only link other production Bunq accounts to projects via OAuth if your main Open Poen Bunq account is also a production account (and vice versa for sandbox accounts)
      - If you want to use a Sandbox Bunq account: create a new Sandbox account and copy the telephone number and login code (its config is written to `bunq-sandbox.conf`; remove this config if you want generate a new Sandbox Bunq account): `docker exec -it poen_app_1 flask bunq create-sandbox-user`
         - Download and install the Bunq Sandbox Android app on your Android smartphone: https://appstore.bunq.com/api/android/builds/bunq-android-sandbox-master.apk
         - Login to your Bunq Sandbox account using the telephone number and login code (000000) which you retrieved using the steps above
      - Edit `config.py` (if you want to use the Sandbox account: set `BUNQ_ENVIRONMENT_TYPE` to `ApiEnvironmentType.SANDBOX`) and add values for `BUNQ_CLIENT_ID` and `BUNQ_CLIENT_SECRET`; you can obtain these from the Bunq (Sandbox) app for Android via 'Profile > Security & Settings > Developers > OAuth > Show client details' and also make sure to add `https://openpoen.nl/` as redirect URL (yes make sure to use 'https' even in the dev/sandbox environment, even though you need to visit openpoen.nl via http:// yourself locally)
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


### Database commands
- `flask database add-user --email <EMAIL_ADDRESS> --admin` adds an admin user (an admin user can create projects on openpoen.nl and can edit a project to connect it to a Bunq bank account)


### Database migration commands
Use these after the database is in production and you need to change the database model.

- After changing the model: `flask db migrate -m <message>`
- Apply the new migration to the database: `flask db upgrade`
- If you need to downgrade: `flask db downgrade`


### Bunq commands
- `flask bunq get-new-payments-all` gets all payments from all IBANs belonging to all projects


## To enter the database
   - `sudo docker exec -it poen_db_1 psql -U <DB_USER> <DB_NAME>` retrieve database user and name from `docker/secrets-db-user.txt` and `docker/secrets-db-name.txt`

## Database architecture
To open the database architecture file `open_poen_architecture.drawio` open it via https://app.diagrams.net/ or via the [desktop app](https://github.com/jgraph/drawio-desktop)
