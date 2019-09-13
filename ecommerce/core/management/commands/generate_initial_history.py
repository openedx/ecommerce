import logging
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Populates the corresponding historical records with"
        "the current state of records which do not have a historical record yet"
    )

    DEFAULT_BATCH_SIZE = 200
    DEFAULT_SLEEP_BETWEEN_INSERTS = 1
    DATE = '2019-06-29'
    HISTORY_USER_ID = 'NULL'
    HISTORY_CHANGE_REASON = 'initial history population'
    TABLE_MAPPING = {
        'offer_benefit': 'offer_historicalbenefit',
        'offer_range': 'offer_historicalrange',
        'offer_rangeproduct': 'offer_historicalrangeproduct',
        'offer_condition': 'offer_historicalcondition',
        'offer_offerassignment': 'offer_historicalofferassignment',
        'catalogue_product': 'catalogue_historicalproduct',
        'catalogue_productattributevalue': 'catalogue_historicalproductattributevalue',
        'order_order': 'order_historicalorder',
        'order_line': 'order_historicalline',
        'partner_stockrecord': 'partner_historicalstockrecord',
        'refund_refund': 'refund_historicalrefund',
        'refund_refundline': 'refund_historicalrefundline',
        'invoice_invoice': 'invoice_historicalinvoice',
        'core_businessclient': 'core_historicalbusinessclient',
        'catalogue_category': 'catalogue_historicalcategory',
        'catalogue_option': 'catalogue_historicaloption',
        'catalogue_productclass': 'catalogue_historicalproductclass',
        'catalogue_productcategory': 'catalogue_historicalproductcategory',
        'catalogue_productattribute': 'catalogue_historicalproductattribute',
        'partner_partner': 'partner_historicalpartner',
    }

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument(
            '--sleep_between',
            default=self.DEFAULT_SLEEP_BETWEEN_INSERTS,
            type=float,
            help='Seconds to sleep between chunked inserts.'
        )

        parser.add_argument(
            "--batchsize",
            action="store",
            default=self.DEFAULT_BATCH_SIZE,
            type=int,
            help="Maximum number of history rows to insert in each batch.",
        )

    def handle(self, *args, **options):
        increment = options['batchsize']
        sleep_between = options['sleep_between']

        for table, historical_table in self.TABLE_MAPPING.items():
            with connection.cursor() as cursor:
                # pylint: disable=all
                query = """
                    SELECT
                        MIN(t.id),
                        MAX(t.id)
                    FROM {table} t
                    LEFT JOIN {historical_table}
                        ON t.id = {historical_table}.id
                    WHERE {historical_table}.id IS NULL
                    """.format(
                        table=table,
                        historical_table=historical_table,
                )
                cursor.execute(query)
                start_id, end_id = cursor.fetchone()
                if not start_id or not end_id:
                    log.info("No records with missing historical records for table %s - skipping.", table)
                    continue
                query = """
                    SELECT
                        column_name
                    FROM information_schema.columns
                    WHERE table_name='{}'
                    ORDER BY ordinal_position
                    """.format(table)
                cursor.execute(query)
                columns = [column[0] for column in cursor.fetchall()]
                # We don't record the AutoSlugField fields in the historical model.
                for column_name in ['slug', 'code']:
                    if column_name in columns:
                        columns.remove(column_name)
                # Quote column names to make sure reserved words do not throw an exception.
                columns = ['`{}`'.format(c) for c in columns]
            while True:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        log.info(
                            "Inserting historical records for %s starting with id %s to %s",
                            table,
                            start_id,
                            start_id + increment - 1,
                        )
                        # xss-lint: disable=python-wrap-html
                        query = """
                            INSERT INTO {historical_table}(
                                {insert_columns},history_date,history_change_reason,history_type,history_user_id
                            )
                            SELECT {select_columns},'{history_date}','{history_change_reason}', '+', {history_user_id}
                            FROM {table} t
                            LEFT JOIN {historical_table}
                                ON t.id={historical_table}.id
                            WHERE {historical_table}.id IS NULL
                                AND t.id >= {start_id}
                                AND t.id < {end_id}
                            """.format(
                                table=table,
                                historical_table=historical_table,
                                insert_columns=','.join(columns),
                                select_columns=','.join(['t.{}'.format(c) for c in columns]),
                                history_date=self.DATE,
                                history_change_reason=self.HISTORY_CHANGE_REASON,
                                history_user_id=self.HISTORY_USER_ID,
                                start_id=start_id,
                                end_id=start_id + increment,
                        )
                        log.info(query)
                        count = cursor.execute(query)
                        log.info("Inserted %s historical records", count)
                start_id += increment
                log.info("Sleeping %s seconds...", sleep_between)
                time.sleep(sleep_between)
                if start_id > end_id:
                    break
