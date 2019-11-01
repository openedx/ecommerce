"""
Management command to backfill history.
"""
import csv
import logging
import os
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Backfill history for models using django-simple-history.
    This is a one-off and would be removed after it is executed.
    Example usage:
    $ ./manage.py backfill_history --batch_size 1000 --sleep_between 1 --input_root /tmp/data/ --settings=devstack
    """

    help = (
        "Populates the historical records with snapshot data."
    )

    DEFAULT_SIZE = 1000
    DEFAULT_SLEEP_BETWEEN_INSERTS = 1
    DATE = '2019-06-29'
    HISTORY_USER_ID = None
    HISTORY_CHANGE_REASON = 'initial history population'

    TABLES = [
        {'name': 'offer_benefit', 'exclude_column': None, 'input_filename': 'offer_benefit_2019-06-29'},
        {'name': 'offer_range', 'exclude_column': 'slug', 'input_filename': 'offer_range_2019-06-29'},
        {'name': 'offer_condition', 'exclude_column': None, 'input_filename': 'offer_condition_2019-06-29'},
        # pylint: disable=C0301
        {'name': 'offer_conditionaloffer', 'exclude_column': 'slug', 'input_filename': 'offer_conditionaloffer_2019-06-29'},
        # pylint: disable=C0301
        {'name': 'offer_offerassignment', 'exclude_column': 'slug', 'input_filename': 'offer_offerassignment_2019-06-29'},
        {'name': 'catalogue_product', 'exclude_column': None, 'input_filename': 'catalogue_product_2019-06-29'},
        # pylint: disable=C0301
        {'name': 'catalogue_productattributevalue', 'exclude_column': None, 'input_filename': 'catalogue_productattributevalue_2019-06-29'},
        {'name': 'order_order', 'exclude_column': None, 'input_filename': 'order_order_2019-06-29'},
        {'name': 'order_line', 'exclude_column': None, 'input_filename': 'order_line_2019-06-29'},
        {'name': 'partner_stockrecord', 'exclude_column': None, 'input_filename': 'partner_stockrecord_2019-06-29'},
        {'name': 'refund_refund', 'exclude_column': None, 'input_filename': 'refund_refund_2019-06-29'},
        {'name': 'refund_refundline', 'exclude_column': None, 'input_filename': 'refund_refundline_2019-06-29'},
        {'name': 'core_businessclient', 'exclude_column': None, 'input_filename': 'core_businessclient_2019-06-29'},
        {'name': 'courses_course', 'exclude_column': None, 'input_filename': 'courses_course_2019-06-29'},
    ]

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument(
            '--sleep_between',
            default=self.DEFAULT_SLEEP_BETWEEN_INSERTS,
            type=float,
            help='Seconds to sleep between chunked inserts.'
        )

        parser.add_argument(
            "--batch_size",
            action="store",
            default=self.DEFAULT_SIZE,
            type=int,
            help="Maximum number of rows per insert.",
        )

        parser.add_argument(
            "--input_root",
            action="store",
            help="Path containing data files from snapshot for history backfill"
        )

    def chunks(self, ids, chunk_size):
        for i in range(0, len(ids), chunk_size):
            yield ids[i:i + chunk_size]

    def replace_values(self, values, original, replacement):
        values = [[replacement if v == original else v for v in value] for value in values]
        return values

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        sleep_between = options['sleep_between']
        input_root = options['input_root']

        for table_info in self.TABLES:
            table = table_info['name']
            historical_table = "_historical".join(table.rsplit('_', 1))
            exclude_column = table_info['exclude_column']
            input_filename = table_info['input_filename']
            file_path = os.path.join(input_root, input_filename)
            history_date = input_filename.rsplit('_')[-1]

            with connection.cursor() as cursor:
                query = u"""
                    SELECT
                        column_name
                    FROM information_schema.columns
                    WHERE table_name='{}'
                    ORDER BY ordinal_position
                    """.format(table)
                cursor.execute(query)
                columns = [column[0] for column in cursor.fetchall()]
            if exclude_column in columns:
                columns.remove(exclude_column)

            with open(file_path, 'r') as input_file:
                reader = csv.DictReader(input_file, delimiter='\x01')
                lines = list(reader)

                for rows in self.chunks(lines, batch_size):
                    row_ids = [row['ID'] for row in rows]
                    if table == 'courses_course':
                        ids = ','.join("'{}'".format(id) for id in row_ids)
                    else:
                        ids = ','.join(row_ids)

                    # Checks for existing historical records
                    with connection.cursor() as cursor:
                        query = u"""
                            SELECT COUNT(1)
                            FROM {historical_table}
                            WHERE ID in ({ids})
                            AND history_type='+'
                            """.format(
                                historical_table=historical_table,
                                ids=ids
                                )  # noqa
                        cursor.execute(query)
                        count = cursor.fetchone()[0]

                    if count == len(rows):
                        log.info(
                            u"Initial history records already exist for ids %s..%s - skipping.",
                            ','.join(row_ids[:2]), ','.join(row_ids[-2:])
                        )
                        continue
                    elif count != 0:
                        raise Exception(u"Database count: %s does not match input count: %s" % (count, len(rows)))

                    values = [[row[column.upper()] for column in columns] for row in rows]

                    # Replace 'NULL' with None
                    values = self.replace_values(values, 'NULL', None)
                    # Replace 'true' with True
                    values = self.replace_values(values, 'true', True)
                    # Replace 'false' with False
                    values = self.replace_values(values, 'false', False)
                    # Add history columns data
                    for value in values:
                        value.extend([history_date, self.HISTORY_CHANGE_REASON, '+', self.HISTORY_USER_ID])
                    # Convert to tuple
                    values = [tuple(row) for row in values]

                    quoted_columns = ['`{}`'.format(c) for c in columns]

                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            log.info(
                                "Inserting historical records for %s starting with id %s to %s",
                                table,
                                row_ids[0],
                                row_ids[-1]
                            )
                            query = u"""
                                INSERT INTO {historical_table}(
                                    {insert_columns},`history_date`,`history_change_reason`,`history_type`,`history_user_id`
                                )
                                VALUES ({placeholder})
                                """.format(
                                    historical_table=historical_table,
                                    insert_columns=','.join(quoted_columns),
                                    placeholder=','.join(['%s'] * (len(columns) + 4))
                                )  # noqa
                            cursor.executemany(query, values)

                    log.info("Sleeping %s seconds...", sleep_between)
                    time.sleep(sleep_between)
