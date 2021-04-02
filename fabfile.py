from fabric import Connection, Config, task
from invoke import Exit
import getpass

# Name of the git repository
GIT_REPO = 'open-poen'

# Path of the directory
DIR = '/home/projects/%s-fryslan' % (GIT_REPO)

# Container used to compile the assets
NODE_CONTAINER = 'openpoenfryslan_node_1'

# App container
APP_CONTAINER = 'openpoenfryslan_app_1'

# Server name
SERVER = 'Oxygen'


@task
def deploy_fryslan(c):
    sudo_pass = getpass.getpass("Enter your sudo password on %s: " % SERVER)
    config = Config(overrides={'sudo': {'password': sudo_pass}})
    c = Connection(SERVER, config=config)

    # Pull from GitHub
    c.run(
        'cd %s && git pull' % (
            DIR
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
    c.sudo('docker exec %s flask db upgrade' % (APP_CONTAINER))

    # Reload app
    c.run('cd %s && touch uwsgi-touch-reload' % (DIR))
