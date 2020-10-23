# -*- coding: utf-8 -*-
import json
import logging
import random
import string
import time
from urllib.parse import urlencode

import ddt
import httpretty
import mock
from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, override_settings
from oscar.test import factories
from requests.exceptions import HTTPError, Timeout
from testfixtures import LogCapture

from ecommerce.core.models import User
from ecommerce.extensions.payment.core.sdn import (
    SDNClient,
    checkSDN,
    checkSDNFallback,
    compare_SDNCheck_vs_fallback,
    extract_country_information,
    populate_sdn_fallback_data,
    populate_sdn_fallback_data_and_metadata,
    populate_sdn_fallback_metadata,
    process_text
)
from ecommerce.extensions.payment.exceptions import SDNFallbackDataEmptyError
from ecommerce.extensions.payment.models import SDNCheckFailure, SDNFallbackData, SDNFallbackMetadata
from ecommerce.extensions.test import factories as extensions_factories
from ecommerce.tests.testcases import TestCase


class SDNCheckTests(TestCase):
    """ Tests for the SDN check function. """

    def setUp(self):
        super(SDNCheckTests, self).setUp()
        self.name = 'Dr. Evil'
        self.city = 'Top-secret lair'
        self.country = 'EL'
        self.user = self.create_user(full_name=self.name)
        self.sdn_api_url = 'http://sdn-test.fake/'
        self.sdn_api_key = 'fake-key'
        self.site_configuration = self.site.siteconfiguration
        self.site_configuration.enable_sdn_check = True
        self.site_configuration.sdn_api_list = 'SDN,TEST'
        self.site_configuration.save()

        self.sdn_validator = SDNClient(
            self.sdn_api_url,
            self.sdn_api_key,
            self.site_configuration.sdn_api_list
        )

    def mock_sdn_response(self, response, status_code=200):
        """ Mock the SDN check API endpoint response. """
        params = urlencode({
            'sources': self.site_configuration.sdn_api_list,
            'api_key': self.sdn_api_key,
            'type': 'individual',
            'name': str(self.name).encode('utf-8'),
            'address': str(self.city).encode('utf-8'),
            'countries': self.country
        })
        sdn_check_url = '{api_url}?{params}'.format(
            api_url=self.sdn_api_url,
            params=params
        )

        httpretty.register_uri(
            httpretty.GET,
            sdn_check_url,
            status=status_code,
            body=response,
            content_type='application/json'
        )

    @httpretty.activate
    @override_settings(SDN_CHECK_REQUEST_TIMEOUT=0.1)
    def test_sdn_check_timeout(self):
        """Verify SDN check logs an exception if the request times out."""
        def mock_timeout(_request, _uri, headers):
            time.sleep(settings.SDN_CHECK_REQUEST_TIMEOUT + 0.1)
            return (200, headers, {'total': 1})

        self.mock_sdn_response(mock_timeout, status_code=200)
        with self.assertRaises(Timeout):
            with mock.patch('ecommerce.extensions.payment.utils.logger.exception') as mock_logger:
                self.sdn_validator.search(self.name, self.city, self.country)
                self.assertTrue(mock_logger.called)

    @httpretty.activate
    def test_sdn_check_connection_error(self):
        """ Verify the check logs an exception in case of a connection error. """
        self.mock_sdn_response(json.dumps({'total': 1}), status_code=400)
        with self.assertRaises(HTTPError):
            with mock.patch('ecommerce.extensions.payment.utils.logger.exception') as mock_logger:
                self.sdn_validator.search(self.name, self.city, self.country)
                self.assertTrue(mock_logger.called)

    @httpretty.activate
    def test_sdn_check_match(self):
        """ Verify the SDN check returns the number of matches and records the match. """
        sdn_response = {'total': 1}
        self.mock_sdn_response(json.dumps(sdn_response))
        response = self.sdn_validator.search(self.name, self.city, self.country)
        self.assertEqual(response, sdn_response)

    @httpretty.activate
    def test_sdn_check_unicode_match(self):
        """ Verify the SDN check returns the number of matches and records the match. """
        sdn_response = {'total': 1}
        self.name = u'Keyser Söze'
        self.mock_sdn_response(json.dumps(sdn_response))
        response = self.sdn_validator.search(self.name, self.city, self.country)
        self.assertEqual(response, sdn_response)

    def test_deactivate_user(self):
        """ Verify an SDN failure is logged. """
        response = {'description': 'Bad dude.'}
        product1 = factories.ProductFactory(stockrecords__partner__short_code='first')
        product2 = factories.ProductFactory(stockrecords__partner__short_code='second')
        basket = factories.BasketFactory(owner=self.user, site=self.site_configuration.site)
        basket.add(product1)
        basket.add(product2)
        self.assertEqual(SDNCheckFailure.objects.count(), 0)
        with mock.patch.object(User, 'deactivate_account') as deactivate_account:
            deactivate_account.return_value = True
            self.sdn_validator.deactivate_user(
                basket,
                self.name,
                self.city,
                self.country,
                response
            )

            self.assertEqual(SDNCheckFailure.objects.count(), 1)
            sdn_object = SDNCheckFailure.objects.first()
            self.assertEqual(sdn_object.full_name, self.name)
            self.assertEqual(sdn_object.city, self.city)
            self.assertEqual(sdn_object.country, self.country)
            self.assertEqual(sdn_object.site, self.site_configuration.site)
            self.assertEqual(sdn_object.sdn_check_response, response)
            self.assertEqual(sdn_object.products.count(), basket.lines.count())
            self.assertIn(product1, sdn_object.products.all())
            self.assertIn(product2, sdn_object.products.all())


@ddt.ddt
class SDNFallbackTests(TestCase):

    LOGGER_NAME = 'ecommerce.extensions.payment.core.sdn'

    def setUp(self):
        super(SDNFallbackTests, self).setUp()
        extensions_factories.SDNFallbackMetadataFactory.create(import_state='Current')
        self.csv_header = """_id,source,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids\n"""  # pylint: disable=line-too-long

    # pylint: disable=line-too-long
    def test_on_examples(self):
        """ Verify the behavior of populate_sdn_fallback_data_and_metadata on some test data """
        csv_string = """_id,source,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids
94734218,Specially Designated Nationals (SDN) - Treasury Department,96663868,Individual,material,Victor Conrad,Dr.,"17472 Christie Stream Apt. 976
North Kristinaport, HI 91033, SN",,,,,,,,,,,,,,https://www.juarez-collier.org/,Wendy Brock,DJ,1944-03-05,Faroe Islands,PK,http://richardson-richardson.org/,CI
37539856,Specially Designated Nationals (SDN) - Treasury Department,55159852,Individual,hotel,Sarah Jones,Mrs.,"3699 Daniel Highway
Port Andrewport, OR 39456, EE",,,,,,,,,,,,,,http://douglas.com/,Misty Johnson,CV,1998-02-15,Ukraine,BO,https://townsend.com/,TM
12650118,Specially Designated Nationals (SDN) - Treasury Department,06283056,Individual,west,Jordan King,Dr.,"0916 Matthew Stream
Nathanhaven, KS 70796, NE",,,,,,,,,,,,,,https://edwards.com/,Luke Soto,VA,2013-12-23,Liechtenstein,AG,http://www.garner.org/,ET
83041181,Specially Designated Nationals (SDN) - Treasury Department,68151959,Individual,together,Joseph Rodriguez,Miss,"Unit 7378 Box 6650
DPO AA 56444, BD",,,,,,,,,,,,,,http://rodriguez.com/,Debra Mcdonald,LS,1990-10-16,Niger,SN,http://howard.net/,BD
53500519,Specially Designated Nationals (SDN) - Treasury Department,96028582,Individual,so,Joshua Weaver,Dr.,"6378 Robin River
Conniechester, AK 67491, CH",,,,,,,,,,,,,,http://www.rose.org/,Chad Carter,PE,1952-02-22,Netherlands Antilles,HN,https://www.fox.com/,SR
02372174,Specially Designated Nationals (SDN) - Treasury Department,28705260,Individual,remain,Joseph Knight,Dr.,"19789 Sims Lodge
North Kara, IL 18127, MX",,,,,,,,,,,,,,http://rodriguez.org/,Katelyn Weaver,MZ,1963-09-28,Germany,BN,https://www.williams.com/,KH
01157291,Specially Designated Nationals (SDN) - Treasury Department,26428901,Individual,happen,Derek Washington,Ms.,"6343 James Circle
New Timothyton, WV 09301, BN",,,,,,,,,,,,,,http://www.davis.com/,Andrew Cordova,PW,1949-10-02,South Africa,LV,http://www.crawford.com/,SR
54139046,Specially Designated Nationals (SDN) - Treasury Department,84007582,Individual,morning,Michelle Fletcher,Dr.,"9402 Nathan Points Apt. 735
Kelleyfort, CA 29232, BB",,,,,,,,,,,,,,http://www.buck.com/,Christopher Tanner,EE,1965-05-06,Israel,BF,http://www.richardson-hill.com/,MA
62040891,Specially Designated Nationals (SDN) - Treasury Department,39940476,Individual,affect,Christopher Adams,Mx.,"1106 Collins Path
Masonfurt, CO 94809, TT",,,,,,,,,,,,,,https://www.lee.com/,Rebecca Romero,TL,1953-12-13,Nepal,HU,https://robinson.org/,OM
09853119,Specially Designated Nationals (SDN) - Treasury Department,89203866,Individual,write,Corey Jacobs,Mx.,"410 Carroll Station Suite 723
Claytonshire, ID 19778, AE",,,,,,,,,,,,,,http://swanson-richardson.com/,Mark Hancock,AM,1977-03-14,Isle of Man,NZ,https://www.mccormick.info/,TV
43915637,Specially Designated Nationals (SDN) - Treasury Department,98733927,Individual,certainly,Ronald Gallagher,Mx.,"9699 Joseph Hill
North Marcusburgh, KS 75288, DJ",,,,,,,,,,,,,,http://brown.biz/,Julie Miller,IR,1971-05-06,Montserrat,HR,https://smith.info/,BZ
45297281,Specially Designated Nationals (SDN) - Treasury Department,00673440,Individual,movement,Bobby Drake,Dr.,"441 Jennifer Brooks
Joshuafort, MD 72104, TH",,,,,,,,,,,,,,https://banks-bender.com/,Michael Anderson,BI,1914-11-05,French Guiana,ST,https://henry.info/,CD"""
        populate_sdn_fallback_data_and_metadata(csv_string)
        self.assertEqual(len(SDNFallbackMetadata.objects.filter()), 2)

        expected_records = [
            ({'victor', 'brock', 'wendy', 'conrad'}, {'91033', '976', 'hi', 'christie', 'apt', 'north', 'kristinaport', 'sn', 'stream', '17472'}, {'SN'}),
            ({'misty', 'sarah', 'johnson', 'jones'}, {'port', 'ee', 'daniel', 'andrewport', '39456', 'highway', 'or', '3699'}, {'EE'}),
            ({'soto', 'luke', 'jordan', 'king'}, {'0916', 'matthew', 'nathanhaven', 'ne', '70796', 'ks', 'stream'}, {'NE'}),
            ({'joseph', 'rodriguez', 'debra', 'mcdonald'}, {'bd', 'dpo', 'unit', '7378', 'box', '56444', '6650', 'aa'}, {'BD'}),
            ({'chad', 'carter', 'joshua', 'weaver'}, {'67491', '6378', 'conniechester', 'ak', 'river', 'ch', 'robin'}, {'CH'}),
            ({'weaver', 'knight', 'joseph', 'katelyn'}, {'il', '19789', 'north', 'kara', 'mx', 'lodge', 'sims', '18127'}, {'MX'}),
            ({'andrew', 'washington', 'derek', 'cordova'}, {'james', 'circle', 'wv', '09301', 'timothyton', 'bn', 'new', '6343'}, {'BN'}),
            ({'christopher', 'michelle', 'tanner', 'fletcher'}, {'points', '735', 'bb', 'apt', 'nathan', '29232', 'kelleyfort', 'ca', '9402'}, {'BB'}),
            ({'adams', 'christopher', 'romero', 'rebecca'}, {'collins', '94809', 'tt', 'co', 'path', 'masonfurt', '1106'}, {'TT'}),
            ({'mark', 'corey', 'jacobs', 'hancock'}, {'claytonshire', '723', '19778', 'station', 'id', '410', 'suite', 'ae', 'carroll'}, {'AE'}),
            ({'gallagher', 'miller', 'ronald', 'julie'}, {'north', 'dj', 'joseph', '9699', 'hill', '75288', 'ks', 'marcusburgh'}, {'DJ'}),
            ({'anderson', 'michael', 'bobby', 'drake'}, {'md', 'joshuafort', '72104', 'brooks', 'jennifer', '441', 'th'}, {'TH'})
        ]
        records = [(set(str(record.names).split()), set(str(record.addresses).split()), set(str(record.countries).split())) for record in SDNFallbackData.objects.all()]
        self.maxDiff = None
        self.assertCountEqual(expected_records, records)

    column_order_changed = """source,_id,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids\n"""
    column_order_changed += """Specially Designated Nationals (SDN) - Treasury Department,94734218,96663868,Individual,material,Victor Conrad,Dr.,"17472 Christie Stream Apt. 976
    North Kristinaport, HI 91033, SN",,,,,,,,,,,,,,https://www.juarez-collier.org/,Wendy Brock,DJ,1944-03-05,Faroe Islands,PK,http://richardson-richardson.org/,CI"""

    new_columns_added = """beep,_id,source,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids\n"""
    new_columns_added += """boop,94734218,Specially Designated Nationals (SDN) - Treasury Department,96663868,Individual,material,Victor Conrad,Dr.,"17472 Christie Stream Apt. 976
    North Kristinaport, HI 91033, SN",,,,,,,,,,,,,,https://www.juarez-collier.org/,Wendy Brock,DJ,1944-03-05,Faroe Islands,PK,http://richardson-richardson.org/,CI"""

    non_essential_columns_removed = """source,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids\n"""
    non_essential_columns_removed += """Specially Designated Nationals (SDN) - Treasury Department,96663868,Individual,material,Victor Conrad,Dr.,"17472 Christie Stream Apt. 976
    North Kristinaport, HI 91033, SN",,,,,,,,,,,,,,https://www.juarez-collier.org/,Wendy Brock,DJ,1944-03-05,Faroe Islands,PK,http://richardson-richardson.org/,CI"""

    @ddt.data(column_order_changed, new_columns_added, non_essential_columns_removed)
    def test_file_format(self, csv_string):
        populate_sdn_fallback_data_and_metadata(csv_string)
        records = SDNFallbackData.get_current_records_and_filter_by_source_and_type('Specially Designated Nationals (SDN) - Treasury Department', 'Individual')
        self.assertEqual(len(records), 1)
        self.assertEqual(process_text(records.first().names), process_text('Victor Conrad Wendy Brock'))
        self.assertEqual(process_text(records.first().addresses), process_text('17472 Christie Stream Apt. 976 North Kristinaport, HI 91033, SN'))
        self.assertEqual(records.first().countries, 'SN')

    def test_checksum_check(self):
        """ Verify that files with the same checksum are not imported
        Verify that files with different checksums are imported. """
        file = self.csv_header + """94734218,Specially Designated Nationals (SDN) - Treasury Department,96663868,Individual,material,Victor Conrad,Dr.,"17472 Christie Stream Apt. 976
        North Kristinaport, HI 91033, SN",,,,,,,,,,,,,,https://www.juarez-collier.org/,Wendy Brock,DJ,1944-03-05,Faroe Islands,PK,http://richardson-richardson.org/,CI"""
        metadata = populate_sdn_fallback_data_and_metadata(file)
        import_timestamp = metadata.import_timestamp
        self.assertNotEqual(metadata.import_timestamp, None)
        metadata = populate_sdn_fallback_data_and_metadata(file)
        self.assertEqual(metadata, None)
        self.assertEqual(import_timestamp, SDNFallbackMetadata.objects.get(import_state="Current").import_timestamp)
        file2 = self.csv_header + """94734219,Specially Designated Nationals (SDN) - Treasury Department,96663868,Individual,material,Victor Conrad,Dr.,"17472 Christie Stream Apt. 976
        North Kristinaport, HI 91033, SN",,,,,,,,,,,,,,https://www.juarez-collier.org/,Wendy Brock,DJ,1944-03-05,Faroe Islands,PK,http://richardson-richardson.org/,CI"""
        metadata = populate_sdn_fallback_data_and_metadata(file2)
        self.assertNotEqual(metadata.import_timestamp, None)
        self.assertNotEqual(import_timestamp, SDNFallbackMetadata.objects.get(import_state="Current").import_timestamp)

    # pylint: enable=line-too-long
    def test_populate_sdn_fallback_metadata(self):
        """ Verify that we are able to correctly create a new metadata entry """
        metadata = populate_sdn_fallback_metadata('test')
        self.assertEqual(len(SDNFallbackMetadata.objects.filter()), 2)
        self.assertEqual(metadata.file_checksum, '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08')
        self.assertEqual(metadata.import_state, 'New')

    def test_populate_sdn_fallback_metadata_into_empty_table(self):
        """ Verify that we are able to correctly create the first metadata entry """
        SDNFallbackMetadata.objects.first().delete()
        with mock.patch('ecommerce.extensions.payment.models.logger.warning') as mock_logger:
            populate_sdn_fallback_metadata('first')
            self.assertTrue(mock_logger.called)
        self.assertEqual(len(SDNFallbackMetadata.objects.filter()), 1)

    def test_populate_sdn_fallback_data(self):
        """ Verify that we are able to correctly import data entries """
        metadata = populate_sdn_fallback_metadata('test')

        csv = self.csv_header
        csv += '\n'.join(
            ','.join(''.join(random.choices(string.ascii_letters, k=10)) for i in range(10)) for i in range(30)
        )
        populate_sdn_fallback_data(csv, metadata)
        self.assertEqual(len(SDNFallbackData.objects.filter()), 30)

    def test_populate_sdn_fallback_data_empty(self):
        """ Verify that we are able to correctly import empty data entries """
        metadata = populate_sdn_fallback_metadata('test')

        # All fields except metadata can be empty when imported
        csv = """_id,source,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids\n"""  # pylint: disable=line-too-long
        csv += (',' * 30 + '\n') * 30

        populate_sdn_fallback_data(csv, metadata)
        self.assertEqual(len(SDNFallbackData.objects.filter()), 30)

    @ddt.data(
        ('bar, MX', '', 'MX'),
        ('bar, MX; bar, BR', '', 'MX BR'),  # check multiple countries in addresses field
        ('bar, MX; bar, BR; bar, MX;', '', 'MX BR'),  # check duplicate countries in addresses field
        ('bar, MX; bar, BR; bar, MX;', 'US, baz', 'MX BR US'),  # check countries from addresses and ids fields
        ('bar, MX; bar, BR; bar, MX;', 'US, baz; DE, baz', 'MX BR US DE'),  # check multiple countries from ids field
        # check duplicate countries from ids field
        ('bar, MX; bar, BR; bar, MX;', 'US, baz; DE, baz; US, baz;', 'MX BR US DE'),
        # check notes included in ids field
        ('bar, MX; bar, BR; bar, MX;', 'US, baz; DE, baz; US, baz; random notes', 'MX BR US DE')
    )
    @ddt.unpack
    def test_extract_country_information(self, addresses, ids, expected_countries):
        """ Verify that extracting the country from the addresses and ids fields behaves as expected """
        countries = extract_country_information(addresses, ids)
        self.assertCountEqual(set(countries.split()), set(expected_countries.split()))

    @ddt.data(
        ('', ''),
        ('foo', {'foo'}),
        ('foo BAR', {'foo', 'bar'}),
        ('BAR foo', {'foo', 'bar'}),
        ('foo BAR !!!', {'foo', 'bar'}),
        ('!foo! !BAR!', {'foo', 'bar'}),
        ('!f!o!o! !B!A!R!', {'f', 'o', 'o', 'b', 'a', 'r'}),
        ('!foo! !BAR! !BAR! !foo!', {'foo', 'bar'}),
        ('Renée Noël François Ruairí Jokūbas KŠthe Nuñez',
            {'nunez', 'renee', 'noel', 'francois', 'ruairi', 'jokubas', 'ksthe'}),
        ('Carl Patiño Jr.', {'carl', 'patino', 'jr'}),
        ('Avenida João XVII Santa Fé New Mexico', {'avenida', 'joao', 'xvii', 'santa', 'fe', 'new', 'mexico'})
    )
    @ddt.unpack
    def test_process_text(self, text, expected_output):
        """ Verify that processing text works as expected (this function is used for names and addresses) """
        output = process_text(text)
        self.assertEqual(output, expected_output)

    @ddt.data(
        ('À Á Â Ã Ä Å à á â ã ä å', {'a'}),
        ('È É Ê Ë è é ê ë', {'e'}),
        ('Ì Í Î Ï ì í î ï', {'i'}),
        ('Ò Ó Ô Õ Ö  ó ô ö õ', {'o'}),
        ('Ù Ú Û Ü ù ú û ü', {'u'}),
        ('Ý ý ÿ', {'y'}),
        ('Ç ç', {'c'}),
        ('Ñ ñ', {'n'}),
        # these cases are here to explicitly note that they are not  transliterated,
        # not to exclude them from transliteration in the future
        ('Ð Æ æ Ø Þ ß þ ð ø', set()),
        ('÷ § § ×   ¶ ¯ ¬', set()),
    )
    @ddt.unpack
    def test_process_text_unicode(self, text, expected_output):
        """ Verify that characters with accents are transliterated correctly."""
        output = process_text(text)
        self.assertEqual(output, expected_output)

    @ddt.data(
        # check order properties
        ('Juan M. de la Cruz', 1),
        ('Cruz la de M. Juan', 1),
        ('nuaJ', 0),
        # check subset properties
        ('Juan', 1),
        ('Cruz', 1),
        ('de', 1),
        ('la', 1),
        ('M.', 1),
        ('M', 1),
        ('Juan de', 1),
        ('Juande', 0),
        # check punctuation properties
        ('la.', 1),
        ('la-', 1),
        ('la}', 1),
        ('Juan-de-la-Cruz,', 1),
        ('Ju-an-de-la-Cruz', 0),
        ('-de-Juan-Cruz-la-', 1),
        ('.dE@jUaN.....CRUZ----!??!?!la.', 1),
        ('Cruz,,,,', 1),
        ('João', 1),
        # check capitalizaiton properties
        ('jUan dE LA CruZ', 1),
        # check frequency properties
        ('Juan de la Cruz Juan de la Cruz', 1),
        ('Juan Juan M. M. de de la la Cruz Cruz', 1),
        # other examples
        ('Juanito', 0),
        ('John de la Cruz', 0),
        ('Wendy', 1),
    )
    @ddt.unpack
    def test_check_sdn_fallback_names(self, name, match):
        """
        Verify that the following properties are true for names:
        1. Order of words doesn’t matter
        2. Number of times that a given word appears doesn’t matter
        3. Punctuation between words or at the beginning/end of a given word doesn’t matter
        4. If a subset of words match, it still counts as a match
        5. Capitalization doesn’t matter
        """
        # pylint: disable=line-too-long
        csv_string = """_id,source,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids
94734218,Specially Designated Nationals (SDN) - Treasury Department,96663868,Individual,material,Juan M. de la Cruz,Dr.,"17472 Christie Stream Apt. 976 North Kristinaport, HI 91033, SN",,,,,,,,,,,,,,https://www.juarez-collier.org/,Wendy João Brock,DJ,1944-03-05,Faroe Islands,PK,http://richardson-richardson.org/,CI"""
        # pylint: enable=line-too-long
        metadata_entry = populate_sdn_fallback_data_and_metadata(csv_string)
        self.assertEqual(checkSDNFallback(name, 'North Kristinaport', 'SN'), match)

    @ddt.data(
        # check order properties
        ('17472 Christie Stream Apt. 976 North Kristinaport, HI 91033, SN', 1),
        ('SN 91033, HI Kristinaport, North 976 Apt. Stream Christie 17472', 1),
        # check subset properties
        ('North', 1),
        ('Kristinaport,', 1),
        # check punctuation properties
        ('Kristinaport', 1),
        ('Kristinaport,,!@#$%^&*()', 1),
        ('Krist%^&*()inaport', False),
        ('João', 1),
        # check capitalizaiton properties
        ('KRISTINAPORT', 1),
        # check frequency properties
        ('Kristinaport Kristinaport', 1),
    )
    @ddt.unpack
    def test_check_sdn_fallback_address(self, address, match):
        """
        Verify that the following properties are true for addresses:
        1. Order of words doesn’t matter
        2. Number of times that a given word appears doesn’t matter
        3. Punctuation between words or at the beginning/end of a given word doesn’t matter
        4. If a subset of words match, it still counts as a match
        5. Capitalization doesn’t matter
        """
        # pylint: disable=line-too-long
        csv_string = """_id,source,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids
94734218,Specially Designated Nationals (SDN) - Treasury Department,96663868,Individual,material,Juan M. de la Cruz,Dr.,"17472 Christie Stream Apt. 976 North Kristinaport João, HI 91033, SN",,,,,,,,,,,,,,https://www.juarez-collier.org/,Wendy Brock,DJ,1944-03-05,Faroe Islands,PK,http://richardson-richardson.org/,CI"""
        # pylint: enable=line-too-long
        metadata_entry = populate_sdn_fallback_data_and_metadata(csv_string)
        self.assertEqual(checkSDNFallback("Juan", address, 'SN'), match)

    def test_check_sdn_fallback_other_fields(self):
        """
        Verify that country, type and source need to match for checkSDNFallback to return True
        """
        # wrong country
        # pylint: disable=line-too-long
        csv_string = """_id,source,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids
94734218,Specially Designated Nationals (SDN) - Treasury Department,96663868,Individual,material,Juan M. de la Cruz,Dr.,"17472 Christie Stream Apt. 976 North Kristinaport, HI 91033, SN",,,,,,,,,,,,,,https://www.juarez-collier.org/,Wendy Brock,DJ,1944-03-05,Faroe Islands,PK,http://richardson-richardson.org/,CI"""
        # pylint: enable=line-too-long
        metadata_entry = populate_sdn_fallback_data_and_metadata(csv_string)
        self.assertEqual(checkSDNFallback("Juan", "Kristinaport", 'AB'), 0)

        # wrong type
        # pylint: disable=line-too-long
        csv_string = """_id,source,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids
94734218,Specially Designated Nationals (SDN) - Treasury Department,96663868,foo,material,Juan M. de la Cruz,Dr.,"17472 Christie Stream Apt. 976 North Kristinaport, HI 91033, SN",,,,,,,,,,,,,,https://www.juarez-collier.org/,Wendy Brock,DJ,1944-03-05,Faroe Islands,PK,http://richardson-richardson.org/,CI"""
        # pylint: enable=line-too-long
        metadata_entry = populate_sdn_fallback_data_and_metadata(csv_string)
        self.assertEqual(checkSDNFallback("Juan", "Kristinaport", 'SN'), 0)

        # wrong source
        # pylint: disable=line-too-long
        csv_string = """_id,source,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids
94734218,bar,96663868,Individual,material,Juan M. de la Cruz,Dr.,"17472 Christie Stream Apt. 976 North Kristinaport, HI 91033, SN",,,,,,,,,,,,,,https://www.juarez-collier.org/,Wendy Brock,DJ,1944-03-05,Faroe Islands,PK,http://richardson-richardson.org/,CI"""
        # pylint: enable=line-too-long
        metadata_entry = populate_sdn_fallback_data_and_metadata(csv_string)
        self.assertEqual(checkSDNFallback("Juan", "Kristinaport", 'SN'), 0)

    @ddt.data(0, 1)
    @mock.patch.object(User, 'deactivate_account')
    @mock.patch('ecommerce.extensions.payment.core.sdn.checkSDNFallback')
    def test_sdn_is_down_sdn_fallback_called(
        self,
        total_hit_count,
        sdn_fallback_mock,
        deactivate_account_mock
    ):
        """
        Verify SDNFallback is called if SDN API returns an error/timeout.
        If hits(s) is >=1, log hit(s) and block the user from making a purchase by deactivating and logging out.
        If there is no hit, allow purchase.
        """
        request = RequestFactory().post('/payment/cybersource/submit/')
        middleware = SessionMiddleware()
        middleware.process_request(request)
        request.session.save()
        site_configuration = self.site.siteconfiguration
        site_configuration.save()
        site_configuration.enable_sdn_check = True
        request.site = site_configuration.site
        request.user = self.create_user(full_name='Juan M. de la Cruz')
        basket = factories.BasketFactory(owner=request.user, site=request.site)
        with mock.patch.object(SDNClient, 'search', side_effect=Timeout):
            logger_name = 'ecommerce.extensions.payment.utils.logger.exception'
            log_message = 'SDNCheck: SDN API call received an error: %s. SDNFallback function called for basket %d' % (str(Timeout), basket.id)
            with self.assertLogs(logger_name, level='INFO') as log:
                sdn_fallback_mock.return_value = total_hit_count
                self.assertEqual(checkSDN(request, 'Juan M. de la Cruz', 'North Kristinaport', 'SN'), total_hit_count)
                logging.getLogger(logger_name).info(log_message)
                assert log_message in log.output[0]
                self.assertTrue(sdn_fallback_mock.called)
                if total_hit_count == 0:
                    self.assertFalse(deactivate_account_mock.called)
                    self.assertTrue(request.user.is_authenticated)
                else:
                    self.assertTrue(deactivate_account_mock.called)
                    self.assertFalse(request.user.is_authenticated)

    def test_sdn_fallback_multiple_hits(self):
        """
        Verify SDNFallback can handle returning multiple hits if it finds a hit more than once.
        """
        csv_string = """_id,source,entity_number,type,programs,name,title,addresses,federal_register_notice,start_date,end_date,standard_order,license_requirement,license_policy,call_sign,vessel_type,gross_tonnage,gross_registered_tonnage,vessel_flag,vessel_owner,remarks,source_list_url,alt_names,citizenships,dates_of_birth,nationalities,places_of_birth,source_information_url,ids
94734218,Specially Designated Nationals (SDN) - Treasury Department,96663868,Individual,material,Juan M. de la Cruz,Dr.,"17472 Christie Stream Apt. 976
North Kristinaport, HI 91033, SN",,,,,,,,,,,,,,https://www.cruz.org/,Wendy Brock,DJ,1944-03-05,Faroe Islands,PK,http://juan.org/,CI
94734219,Specially Designated Nationals (SDN) - Treasury Department,96663869,Individual,material,Juan Cruz,Dr.,"123 Main Street
North Kristinaport, HI 91033, SN",,,,,,,,,,,,,,https://www.juarez-collier.org/,Wendy Brock,DJ,1944-03-05,Faroe Islands,PK,http://richardson-richardson.org/,CI
37539856,Specially Designated Nationals (SDN) - Treasury Department,55159852,Individual,hotel,Sarah Jones,Mrs.,"3699 Daniel Highway
Port Andrewport, OR 39456, EE",,,,,,,,,,,,,,http://douglas.com/,Misty Johnson,CV,1998-02-15,Ukraine,BO,https://townsend.com/,TM"""
        populate_sdn_fallback_data_and_metadata(csv_string)
        sdn_fallback_hit_count = checkSDNFallback('Juan Cruz', 'North Kristinaport', 'SN')
        self.assertEqual(sdn_fallback_hit_count, 2)

    def test_compare_SDNCheck_vs_fallback_match_no_hit(self):
        """Log correct results from fallback and API calls: matching, no hit
        We'll use form data not matching fallback csv data, and pass 0 hits from the SDN API"""

        form_data = {
            'basket': 999,
            'first_name': 'Test',
            'last_name': 'User',
            'city': 'Cambridge',
            'country': 'US',
        }

        with LogCapture(self.LOGGER_NAME) as log_miss:
            compare_SDNCheck_vs_fallback(form_data['basket'], form_data, 0)
            log_miss.check(
                (
                    self.LOGGER_NAME,
                    'INFO',
                    "SDNFallback compare: MATCH. Results - SDN API: 0 hit(s); SDN Fallback: 0 hit(s). Basket: " +
                    str(form_data['basket'])
                )
            )

    def test_compare_SDNCheck_vs_fallback_mismatch(self):
        """Log correct results from fallback and API calls: mismatch where API hit is missed in fallback
        We'll use form data not matching fallback csv data, and pass 1 hit from the SDN API"""

        form_data = {
            'basket': 999,
            'first_name': 'Test',
            'last_name': 'User',
            'city': 'Cambridge',
            'country': 'US',
        }

        with LogCapture(self.LOGGER_NAME) as log_mismatch:
            compare_SDNCheck_vs_fallback(form_data['basket'], form_data, 1)
            log_mismatch.check(
                (
                    self.LOGGER_NAME,
                    'INFO',
                    "SDNFallback compare: MISMATCH. Results - SDN API: 1 hit(s); SDN Fallback: 0 hit(s). Basket: " +
                    str(form_data['basket'])
                ),
                (
                    self.LOGGER_NAME,
                    'INFO',
                    "Failed SDN match for first name: Test, last name: User, city: Cambridge, country: US "
                )
            )


class SDNFallbackTestsWithoutSetup(TestCase):
    def test_SDNFallback_empty_data(self):
        """
        when checkSDNFallback is called and data isn't populated, we throw the expected Exception
        """
        with self.assertRaises(SDNFallbackDataEmptyError):
            checkSDNFallback('Juan', 'North Kristinaport', 'SN')
