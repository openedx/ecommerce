"""
Django management command to load the lms_user_id column from historical data.
"""


import logging

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.models import Max

User = apps.get_model('core', 'User')
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Import username/lms_user_id mappings into the lms_user_id column.

    Export data for this by running this query from the LMS:
        SELECT *
        INTO OUTFILE 'test_users.csv'
        FIELDS TERMINATED BY ','
        OPTIONALLY ENCLOSED BY '"'
        LINES TERMINATED BY '\n'
        FROM (
            SELECT
                username,
                id as user_id
            FROM auth_user
            WHERE id NOT IN (
                SELECT user_id FROM user_api_userretirementstatus
            )
            UNION SELECT
                original_username AS username,
                user_id
            FROM user_api_userretirementstatus
        ) u

    Import data into ecommerce using:

    CREATE TABLE temp_username_userid
    (
    username VARCHAR(150),
    lms_user_id INT(11),
    PRIMARY KEY(lms_user_id)
    )
    ENGINE = InnoDB;

    LOAD DATA FROM S3 FILE 's3-BUCKET_ID/username_userid'
    INTO TABLE temp_username_userid
    FIELDS TERMINATED BY ','
    OPTIONALLY ENCLOSED BY '"'
    LINES TERMINATED BY '\n'
        (username, lms_user_id)

    CREATE INDEX username_index ON temp_username_userid (username);
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-user-id',
            type=int,
            default=None,
            help="Maximum user id to update"
        )
        parser.add_argument(
            '--starting-user-id',
            type=int,
            default=0,
            help="First user id to update"
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10000,
            help="Number of users to update at a time",
        )

    def handle(self, *args, **options):

        max_user_id = options.get('max_user_id')

        if max_user_id is None:
            max_user_id = User.objects.aggregate(Max('id'))['id__max']

        increment = options['batch_size']
        starting_user_id = options['starting_user_id']

        while True:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    update_count = cursor.execute(
                        """
                        UPDATE ecommerce_user eu
                        JOIN temp_username_userid tuu
                        ON eu.username = tuu.username
                        SET eu.lms_user_id = tuu.lms_user_id
                        WHERE eu.id >= %s AND eu.id < %s
                        AND eu.lms_user_id IS NULL
                        """,
                        (
                            starting_user_id,
                            min(starting_user_id + increment, max_user_id + 1)
                        )
                    )
            self.stdout.write(
                self.style.SUCCESS(
                    'Updated {} rows, starting at {}'.format(update_count, starting_user_id)
                )
            )
            starting_user_id += increment
            if starting_user_id > max_user_id:
                break

        self.stdout.write(self.style.SUCCESS('Import complete'))
