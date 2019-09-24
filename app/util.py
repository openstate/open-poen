from os.path import abspath, join, dirname
from time import sleep
import json
import socket
import sys

from app import app, db
from app.models import Payment, Project, Subproject, IBAN

from bunq.sdk.context import ApiContext
from bunq.sdk.context import ApiEnvironmentType
from bunq.sdk.model.generated import endpoint

sys.path.insert(0, abspath(join(dirname(__file__), '../tinker/tinker')))
from libs.bunq_lib import BunqLib


def create_bunq_api_config(bunq_access_token, project_id):
    environment = app.config['BUNQ_ENVIRONMENT_TYPE']

    filename = 'bunq-production'
    if environment == ApiEnvironmentType.SANDBOX:
        filename = 'bunq-sandbox'

    api_context = ApiContext(
        environment, bunq_access_token, socket.gethostname()
    ).save('%s-project-%s.conf' % (filename, project_id))


def get_bunq_api_config_filename(environment_type, project_id):
    filename_base = 'bunq-production'
    if environment_type == ApiEnvironmentType.SANDBOX:
        filename_base = 'bunq-sandbox'

    return '%s-project-%s.conf' % (filename_base, project_id)


def get_all_monetary_account_active(project_id):
    environment_type = app.config['BUNQ_ENVIRONMENT_TYPE']
    filename = get_bunq_api_config_filename(environment_type, project_id)
    bunq_api = BunqLib(environment_type, conf=filename)
    return bunq_api.get_all_monetary_account_active()


def get_all_monetary_account_active_ibans(project_id):
    # Remove any already existing IBANs for this project
    IBAN.query.filter_by(project_id=project_id).delete()

    new_ibans_count = 0
    for monetary_account in get_all_monetary_account_active(project_id):
        for alias in monetary_account._alias:
            if alias._type_ == 'IBAN':
                new_iban = IBAN(
                    project_id=project_id,
                    iban=alias._value,
                    iban_name=monetary_account._description
                )
                db.session.add(new_iban)
                new_ibans_count += 1
    db.session.commit()
    return new_ibans_count


def _transform_payment(payment):
    payment_as_dict = json.loads(payment.to_json())
    result = {}
    for k, v in payment_as_dict.items():
        # Skip these fields as we don't use them
        if k in ['allow_chat', 'attachment',
                 'request_reference_split_the_bill']:
            continue

        # Rename the 'id' field
        if k == 'id':
            k = 'bank_payment_id'

        # flatten dicts
        if type(v) == dict:
            for k2, v2 in v.items():
                f = "%s_%s" % (k, k2)
                result[f] = v2
        else:
            result[k] = v
    return result


def get_new_payments(project_id):
    # Loop over all monetary accounts (i.e., all IBANs belonging to one
    # Bunq account)
    for monetary_account in get_all_monetary_account_active(project_id):
        new_payments_count = 0
        new_payments = True
        payments = None
        # Use a while loop because of pagination; stop when we find a
        # payment that already exists in our database or if no new
        # payments are found or in case of an error
        while new_payments:
            # Retrieve payments from Bunq
            try:
                if payments:
                    params = payments.pagination.url_params_previous_page
                else:
                    params = {'count': 10}

                # Bunq allows max 3 requests per 3 seconds
                sleep(1)
                payments = endpoint.Payment.list(
                    monetary_account_id=monetary_account._id_,
                    params=params
                )
            except Exception as e:
                app.logger.error(
                    "Getting Bunq payments resulted in an exception:"
                )
                app.logger.error(e)
                new_payments = False
                continue

            if not payments.value:
                new_payments = False
                continue

            # Save payments to database
            for full_payment in payments.value:
                try:
                    payment = _transform_payment(full_payment)
                except Exception as e:
                    app.logger.error(
                        "Transforming a Bunq payment resulted in an exception:"
                    )
                    app.logger.error(e)
                    new_payments = False
                    continue
                try:
                    existing_payment = Payment.query.filter_by(
                        bank_payment_id=payment['bank_payment_id']
                    ).first()

                    if existing_payment:
                        new_payments = False
                    else:
                        project = Project.query.filter_by(
                            iban=payment['alias_value']
                        ).first()
                        if project:
                            payment['project_id'] = project.id

                        subproject = Subproject.query.filter_by(
                            iban=payment['alias_value']
                        ).first()
                        if subproject:
                            payment['subproject_id'] = subproject.id

                        p = Payment(**payment)
                        db.session.add(p)
                        db.session.commit()
                        new_payments_count += 1
                except Exception as e:
                    app.logger.error(
                        "Saving a Bunq payment resulted in an exception:"
                    )
                    app.logger.error(e)
                    new_payments = False
                    continue

            if not payments.pagination.has_previous_page():
                new_payments = False

        # Log the number of retrieved payments
        iban = ''
        iban_name = ''
        for alias in monetary_account._alias:
            if alias._type_ == 'IBAN':
                iban = alias._value
                iban_name = alias._name
        app.logger.info(
            'Project %s: retrieved %s payments for %s (%s)' % (
                project_id, new_payments_count, iban, iban_name
            )
        )


def human_format(num):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0

    if magnitude > 0:
        return '%.1f%s' % (num, ['', 'K', 'M'][magnitude])
    else:
        return round(num)


def format_currency(num):
    return f'€ {round(num):,}'
