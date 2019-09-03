from fabric.api import run, env, cd, sudo

env.use_ssh_config = True
env.hosts = ["Oxygen"]


def deploy():
    with cd('/home/projects/open-poen'):
        run('git pull git@github.com:openstate/open-poen.git')
        run('sudo docker exec poen_node_1 yarn prod')
        run('touch uwsgi-touch-reload')
        #sudo('docker exec poen_nginx_1 nginx -s reload')
