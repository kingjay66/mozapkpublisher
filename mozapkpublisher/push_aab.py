#!/usr/bin/env python3

import argparse
import logging

from mozapkpublisher.common import main_logging
from mozapkpublisher.common.aab import add_aab_checks_arguments, extract_and_check_aabs_metadata
from mozapkpublisher.common.exceptions import WrongArgumentGiven
from mozapkpublisher.common.store import GooglePlayEdit

logger = logging.getLogger(__name__)


_STORE_PER_TARGET_PLATFORM = {
    'google': GooglePlayEdit,
}


def push_aab(
    aabs,
    target_store,
    username,
    secret,
    track=None,
    rollout_percentage=None,
    dry_run=True,
    contact_server=True,
):
    """
    Args:
        aabs: list of AAB files
        target_store (str): must be "google", for now
        username (str): Google Play service account or Amazon Store client ID
        secret (str): Filename of Google Play Credentials file or contents of Amazon Store
            client secret
        track (str): (only when `target_store` is "google") Google Play track to deploy
            to (e.g.: "nightly"). If "rollout" is chosen, the parameter `rollout_percentage` must
            be specified as well
        rollout_percentage (int): percentage of users to roll out this update to. Must be a number
            in (0-100]. This option is only valid if `target_store` is "google" and
            `track` is set to "rollout"
        dry_run (bool): `True` to do a dry-run
        contact_server (bool): `False` to avoid communicating with the Google Play server.
            Useful if you're using mock credentials.
    """
    if target_store != "google":
        raise WrongArgumentGiven('Only the Google store is currently supported for AAB')
    if track is None:
        # The Google store allows multiple stability "tracks" to exist for a single app, so it
        # requires you to disambiguate which track you'd like to publish to.
        raise WrongArgumentGiven('When "target_store" is "google", the track must be provided')

    # We want to tune down some logs, even when push_aab() isn't called from the command line
    main_logging.init()

    aabs_metadata_per_paths = extract_and_check_aabs_metadata(aabs)

    update_aab_kwargs = {
        kwarg_name: kwarg_value
        for kwarg_name, kwarg_value in (
            ('track', track),
            ('rollout_percentage', rollout_percentage)
        )
        if kwarg_value
    }

    # Each distinct product must be uploaded in different "edit"/transaction, so we split them
    # by package name here.
    aabs_by_package_name = _aabs_by_package_name(aabs_metadata_per_paths)
    for package_name, extracted_aabs in aabs_by_package_name.items():
        store = _STORE_PER_TARGET_PLATFORM[target_store]
        with store.transaction(username, secret, package_name, contact_server=contact_server,
                               dry_run=dry_run) as edit:
            edit.update_aab(extracted_aabs, **update_aab_kwargs)


def _aabs_by_package_name(aabs_metadata):
    aab_package_names = {}
    for (aab, metadata) in aabs_metadata.items():
        package_name = metadata['package_name']
        if package_name not in aab_package_names:
            aab_package_names[package_name] = []
        aab_package_names[package_name].append((aab, metadata))

    return aab_package_names


def main():
    parser = argparse.ArgumentParser(description='Upload AABs on the Google Play Store.')

    subparsers = parser.add_subparsers(dest='target_store', title='Target Store')

    google_parser = subparsers.add_parser('google')
    google_parser.add_argument('track', help='Track on which to upload')
    google_parser.add_argument(
        '--rollout-percentage',
        type=int,
        choices=range(0, 101),
        metavar='[0-100]',
        default=None,
        help='The percentage of users who will get the update. Specify only if track is rollout'
    )
    google_parser.add_argument('--commit', action='store_false', dest='dry_run',
                               help='Commit new release on Google Play. This action cannot be '
                                    'reverted')

    parser.add_argument('--username', required=True,
                        help='The google service account')
    parser.add_argument('--secret', required=True,
                        help='The file that contains google credentials')
    parser.add_argument('--do-not-contact-server', action='store_false', dest='contact_server',
                        help='''Prevent any request to reach the AAB server. Use this option if
you want to run the script without any valid credentials nor valid AABs. --service-account and
--credentials must still be provided (you can just fill them with random string and file).''')
    add_aab_checks_arguments(parser)
    config = parser.parse_args()

    if config.target_store == 'google':
        track = config.track
        rollout_percentage = config.rollout_percentage
    else:
        track = None
        rollout_percentage = None

    try:
        push_aab(
            config.aabs,
            config.target_store,
            config.username,
            config.secret,
            track,
            rollout_percentage,
            config.dry_run,
            config.contact_server,
        )
    except WrongArgumentGiven as e:
        parser.error(e)


__name__ == '__main__' and main()
