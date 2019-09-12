import socket

from app import app

from bunq.sdk.context import ApiContext
from bunq.sdk.context import ApiEnvironmentType


def create_bunq_api_config(bunq_access_token, project_id):
    environment = app.config['BUNQ_ENVIRONMENT_TYPE']

    filename = 'bunq-production'
    if environment == ApiEnvironmentType.SANDBOX:
        filename = 'bunq-sandbox'

    api_context = ApiContext(
        environment, bunq_access_token, socket.gethostname()
    )
    api_context.save('%s-project-%s.conf' % (filename, project_id))


def get_bunq_api_config_filename(environment_type, project_id):
    filename_base = 'bunq-production'
    if environment_type == ApiEnvironmentType.SANDBOX:
        filename_base = 'bunq-sandbox'

    return '%s-project-%s.conf' % (filename_base, project_id)
