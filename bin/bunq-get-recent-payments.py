#!/usr/bin/env python
import sys
import os
from os.path import abspath, join, dirname
from pprint import pprint
import json

sys.path.insert(0, abspath(join(dirname(__file__), '../tinker/tinker')))

from libs.bunq_lib import BunqLib
from libs.share_lib import ShareLib
from bunq.sdk.context import ApiEnvironmentType


def transform(payment):
    payment_as_dict = json.loads(payment.to_json())
    result = {}
    for k,v in payment_as_dict.items():
        if type(v) == dict:
            for k2, v2 in v.items():
                f = "%s_%s" % (k, k2,)
                result[f] = v2
        else:
            result[k] = v
    return result


def store(payment):
    pprint(payment)


def main():
    all_option = ShareLib.parse_all_option()
    environment_type = ShareLib.determine_environment_type_from_all_option(all_option)

    bunq = BunqLib(environment_type)

    try:
        all_payments = bunq.get_all_payment(10)
    except Exception as e:
        print("Getting bunq payments resulted in an exception:")
        print(e)
        all_payments = []

    for p in all_payments:
        try:
            payload = transform(p)
        except Exception as e:
            print("Transforming a bunq payment resulted in an exception:")
            print(e)
            payload = {}
        try:
            store(payload)
        except Exception as e:
            print("Saving a bunq payment resulted in an exception:")
            print(e)

    if environment_type is ApiEnvironmentType.SANDBOX:
        all_alias = bunq.get_all_user_alias()
        ShareLib.print_all_user_alias(all_alias)

    bunq.update_context()


if __name__ == '__main__':
    main()
