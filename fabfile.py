from fabric import Connection, Config, task
from invoke import Exit
import getpass

# Name of the git repository
GIT_REPO = 'open-poen'

# Path of the directory
DIR = '/home/projects/%s' % (GIT_REPO)
DIR_CORONA = '/home/projects/%s-corona' % (GIT_REPO)

# Container used to compile the assets
NODE_CONTAINER = 'poen_node_1'
NODE_CONTAINER_CORONA = 'openpoencorona_node_1'

# App container
APP_CONTAINER = 'poen_app_1'
APP_CONTAINER_CORONA = 'openpoencorona_app_1'

# Server name
SERVER = 'Oxygen'


@task
def deploy(c):
    sudo_pass = getpass.getpass("Enter your sudo password on %s: " % SERVER)
    config = Config(overrides={'sudo': {'password': sudo_pass}})
    c = Connection(SERVER, config=config)

    # Pull from GitHub
    c.run(
        'bash -c "cd %s && git pull git@github.com:openstate/%s.git"' % (
            DIR,
            GIT_REPO
        )
    )

    # Compile assets
    output = c.sudo(
        'docker inspect --format="{{.State.Status}}" %s' % (NODE_CONTAINER)
    )
    if output.stdout.strip() != 'running':
        raise Exit(
            '\n*** ERROR: The %s container, used to compile the assets, is '
            'not running. Please build/run/start the container.' % (
                NODE_CONTAINER
            )
        )
    c.sudo('docker exec %s yarn' % (NODE_CONTAINER))
    c.sudo('docker exec %s yarn prod' % (NODE_CONTAINER))

    # Upgrade database
    #c.sudo('docker exec %s flask db upgrade' % (APP_CONTAINER))

    # Reload app
    c.run('bash -c "cd %s && touch uwsgi-touch-reload"' % (DIR))


@task
def deploy_corona(c):
    sudo_pass = getpass.getpass("Enter your sudo password on %s: " % SERVER)
    config = Config(overrides={'sudo': {'password': sudo_pass}})
    c = Connection(SERVER, config=config)

    # Pull from GitHub
    print('bash -c "cd %s && git pull git@github.com:openstate/%s.git"' % (
            DIR_CORONA,
            GIT_REPO
        )
    )
    c.run(
        'bash -c "cd %s && git pull git@github.com:openstate/%s.git"' % (
            DIR_CORONA,
            GIT_REPO
        )
    )

    # Compile assets
    output = c.sudo(
        'docker inspect --format="{{.State.Status}}" %s' % (NODE_CONTAINER_CORONA)
    )
    if output.stdout.strip() != 'running':
        raise Exit(
            '\n*** ERROR: The %s container, used to compile the assets, is '
            'not running. Please build/run/start the container.' % (
                NODE_CONTAINER_CORONA
            )
        )
    c.sudo('docker exec %s yarn' % (NODE_CONTAINER_CORONA))
    c.sudo('docker exec %s yarn prod' % (NODE_CONTAINER_CORONA))

    # Upgrade database
    #c.sudo('docker exec %s flask db upgrade' % (APP_CONTAINER))

    # Reload app
    c.run('bash -c "cd %s && touch uwsgi-touch-reload"' % (DIR_CORONA))
