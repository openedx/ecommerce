# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from collections import namedtuple, OrderedDict
import csv
import datetime
import logging
from optparse import make_option
import os
import random
import requests
import tempfile
import urlparse

from django.core.mail import EmailMultiAlternatives
from django.core.management import BaseCommand, CommandError
from django.conf import settings

from oscar.core.loading import get_model

from ecommerce.courses.models import Course

Line = get_model('order', 'Line')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
Partner = get_model('partner', 'Partner')
Refund = get_model('refund', 'Refund')
Source = get_model('payment', 'Source')

logger = logging.getLogger(__name__)

PAYBOX_DIRECT_URL = settings.PAYMENT_PROCESSOR_CONFIG['paybox_system']['PAYBOX_DIRECT_URL']
SITE = settings.PAYMENT_PROCESSOR_CONFIG['paybox_system']['PBX_SITE']
RANG = settings.PAYMENT_PROCESSOR_CONFIG['paybox_system']['PBX_RANG']
IDENTIFIANT = settings.PAYMENT_PROCESSOR_CONFIG['paybox_system']['PBX_IDENTIFIANT']
CLE = settings.PAYMENT_PROCESSOR_CONFIG['paybox_system']['CLE']


class Command(BaseCommand):
    """Publish the courses to LMS."""

    help = 'Export orders'
    option_list = BaseCommand.option_list + (
        make_option(
            '--count',
            action='store_true',
            dest='count',
            default=False,
            help='Return transaction count'
        ),
        make_option(
            '--paybox',
            action='store_true',
            dest='paybox',
            default=False,
            help='Control transaction from Paybox'
        ),
        make_option(
            '--start-date',
            action='store',
            dest='start-date',
            default=None,
            help='Start date (format MM-DD-YYYY)'
        ),
        make_option(
            '--end-date',
            action='store',
            dest='end-date',
            default=None,
            help='End date (format MM-DD-YYYY)'
        ),
        make_option(
            '--email',
            action='store',
            dest='email',
            default=None,
            help='Email to send CSV file'
        ),
    )

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    def get_paybox_transaction(self, paybox_ref):
        """Retrieve from Paybox Direct API information about transaction.
           {'CODEREPONSE': '00000', 'STATUS': 'Rembours\xe9', 'RANG': '01', 'AUTORISATION': '941106',
            'NUMTRANS': '0621673735', 'REMISE': '621810243', 'COMMENTAIRE': 'Demande trait\xe9e avec succ\xe8s',
            'SITE': '2357367', 'NUMAPPEL': '0625734806', 'NUMQUESTION': '0546312268'}
        """
        data = {}
        data['SITE'] = SITE
        data['RANG'] = RANG
        data['IDENTIFIANT'] = IDENTIFIANT
        data['CLE'] = CLE
        data['VERSION'] = '00103'  # Paybox Direct
        data['TYPE'] = '00017'
        data['DATEQ'] = datetime.datetime.now().strftime('%d%m%Y%H%M%S')
        data['NUMQUESTION'] = '%.10d' % random.randint(1, 1000000000)
        data['NUMTRANS'] = str(paybox_ref)
        response = requests.post(PAYBOX_DIRECT_URL, data)

        return {k: v.decode('ISO-8859-2') for k, v in dict(urlparse.parse_qsl(response.content)).items()}

    def get_queryset(self, options):
        order_queryset = Order.objects.filter(status='Complete', total_excl_tax__gt=0).order_by('date_placed')
        if options['start-date']:
            try:
                start_date = datetime.datetime.strptime(options['start-date'], '%m-%d-%Y')
                order_queryset = order_queryset.filter(date_placed__gte=start_date)
            except ValueError:
                raise CommandError(u"Start date must be of format MM-DD-YYYY")

        if options['end-date']:
            try:
                end_date = datetime.datetime.strptime(options['end-date'], '%m-%d-%Y')
                order_queryset = order_queryset.filter(date_placed__gte=end_date)
            except ValueError:
                raise CommandError(u"End date must be of format MM-DD-YYYY")

        return order_queryset

    def create_csv(self, csv_header, rows):

        handle, filename = tempfile.mkstemp(prefix='export_factures_', suffix='.csv')
        with os.fdopen(handle, 'w') as file:
            writer = csv.writer(file)
            writer.writerow([field.encode('utf-8') for field in csv_header])

            for row in rows:
                row_converted = []
                for s in row:
                    try:
                        row_converted.append(s.encode("utf8"))
                    except AttributeError:
                        row_converted.append(u"{}".format(s))

                writer.writerow(row_converted)
        return filename

    def send_email(self, recipient, csv_filename):
        email = EmailMultiAlternatives(
                subject=u"Relevé des paiements FUN",
                body=u"Relevé des paiements FUN",
                from_email=settings.SERVER_EMAIL,
                to=[recipient],)
        email.attach_file(csv_filename)
        try:
            email.send()
            self.stdout.write(u"Email sent to {recipient}".format(recipient=recipient))
        except:
            raise CommandError(u"CSV could not be sent to {recipient}".format(recipient=recipient))

    def handle(self, *args, **options):
        fields = [
            ('date', u"Date Facture"),
            ('number', u"Ref FUN"),
            ('paybox_ref', u"Ref Paybox"),
            ('user_username', u"Utilsateur"),
            ('user_email', u"Email"),
            ('user_name', u"Nom"),
            ('total_incl_tax', u"Total TTC"),
            ('total_excl_tax', u"Total TTC"),
            ('course_key', u"Ref cours"),
            ('course_name', u"Nom du cours"),
            ('refund_status', "Remboursement FUN"),
            ('refund_asked', u"Date demande remboursement"),
            ('refund_answered', u"Date traitement remboursement"),
            ('status_paybox', u"Etat Paybox"),
            ('remise_paybox', u"Remise Paybox"),
            ('comment_paybox', u"Commentaire"),
            ]

        orders = []
        ordertupple = namedtuple('OrderTuple', OrderedDict(fields).keys())

        courses = {course['id']: course['name'] for course in Course.objects.all().values()}

        order_queryset = self.get_queryset(options)
        if options['count']:
            self.stdout.write(u"Transaction count: {count}".format(count=order_queryset.count()))
            return

        for order in order_queryset:
            course_name = ''
            refund_status = ''
            refund_date = ''
            refund_answered = ''
            paybox_ref = order.sources.all()[0].reference
            try:
                #paybox_ref = order.sources.all()[0].reference
                product = order.lines.first().product
                course_key = product.attribute_values.get(attribute__name='course_key').value
                course_name = courses[course_key]
            except Exception as e:
                course_key = "le produit n'existe plus (%r)" % e  # this should not happen

            # if a refund exixts we also want to know when it was processed
            if order.refunds.exists():
                refund = order.refunds.all()[0]
                refund_status = refund.status
                refund_date = refund.created
                refund_answered = refund.history.latest().created if refund.history.count() > 1 else ''

            if options['paybox']:
                paybox = self.get_paybox_transaction(paybox_ref)
            else:
                paybox = {'STATUS': '', 'REMISE': '', 'COMMENTAIRE': '',}

            order_data = ordertupple(
                date=order.date_placed,
                number=order.number,
                paybox_ref=paybox_ref,
                user_username=order.user.username,
                user_email=order.user.email,
                user_name=order.user.get_full_name(),
                total_incl_tax=order.total_incl_tax,
                total_excl_tax=order.total_excl_tax,
                course_key=course_key,
                course_name=course_name,
                refund_status=refund_status,
                refund_asked=refund_date,
                refund_answered=refund_answered,
                status_paybox=paybox['STATUS'],
                remise_paybox=paybox['REMISE'],
                comment_paybox=paybox['COMMENTAIRE'],
                )
            orders.append(order_data)
            logger.info(order_data)

        filename = self.create_csv(OrderedDict(fields).values(), orders)
        self.stdout.write(u"CSV File saved to {name}".format(name=filename))
        if options['email']:
            self.send_email(options['email'], filename)
