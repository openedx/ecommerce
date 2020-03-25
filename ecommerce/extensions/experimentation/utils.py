"""
Experimentation utilities
"""

import hashlib
import logging
import re

logger = logging.getLogger(__name__)

SKUS_IN_EXPERIMENT = ['8017833', 'EE1CB04', 'BC6BBAA', '7470902', 'E657925', 'F7291B5', '9941E53', 'B8B57E5', '8D399AE', '68A1E24', 'B3336CB', 'C6730F7', '618D3B6', 'E7B7033', '93557DA', '20F47A4', '4FE34FB', 'B83FD08', '656458A', '148E53C', '6B46BF1', '7526CED', '2AEFD99', 'FFFC863', '7508520', '65B746A', 'B00FA09', '5BCCB48', 'A9C4D26', '1F61A90', 'F8EB55F', '68FBFA6', '6CB91FD', '1049A7D', 'F1C5143', 'FAEA42A', '0770C0B', '482C0BB', '089EAAB', 'FC3205B', '35F2C9C', 'E4CCAD3', '4214003', '4A559DF', '164475D', '91BA616', '8500D5F', 'E263050', '27EB505', 'F03831A', '81FE29C', '9D44A40', 'C0140D5', '78D2930', 'D22FD32', 'DEC87C6', 'FE51C56', 'BB2784F', '4573945', '2BBEE56', 'A95601F', '009CA20', '55CEE9A', '1ED3F94', '1B9EC41', '7589F32', 'B45F9A3', '122C8E1', '18AD676', '1E56B30', '5C5505B', 'BF4DCCD', 'FF92E92', '24522B4', 'A46923A', '54FA8FB', '96A027C', 'BB9105D', '5068BB6', '89763D1', 'A4038BB', 'A472927', '7B4A192', '64EAE78', 'CA1DE0D', '949787E', 'F340A62', '6A91F09', '1D510D4', 'D1784FC', '6D55AAD', '26A2598', '4BC3573', '6607806', 'D1F4643', 'DBC4D64', '969A888', '0F0DA06', 'C8F2BBC', 'F65F7B9', 'D182352', '345BFE3', '4F80AAC', '21B09B8', '9BBBEDB', '174E20E', '19352C1', '297CE5D', 'CEAAD2F', '135F2CD', '00E6293', '0E651C0', '2044189', '4E954A8', '51A8136', '9655325', '8EEF03E', 'D4F47A0', '385BA02', 'F19DBD9', '9F72772', 'D4211FD', 'FACE8A9', '4E4692F', 'BE103E5', 'F245C3C', 'F3E679F', '52BA096', '5C79AD4', 'E2FED0A', 'F6585A6', '7373203', '609F7EE', '5C30778', '9E0691A', '2BA05C8', '9ED4FF6', 'E869539', '08B177B', '9797854', '261ABF2', 'E332E87', 'F0E5571', 'F7737F9', '3C3F384', '68B477E', '3606BB9', '4B565D8', 'C22CB6B', 'E5521D8', 'B142574', 'CEB0CBB', '77D34DB', '5698055', '3A28450', 'CD8FE5C', '7FFDBEC', '1C3EDA6', 'C8F8003', '0418B6C', 'EB8B605', '0F34DBB', '0BC4166', '32CBC4B', '2AAADA7', 'D15C527', '2B9CDE8', '87D0CF2', '78F65E1', 'E03F47D', '8F821E5', 'C0116EF', 'BA55D54', 'EB5A83D', 'E3C02F2', 'CA59F18', '787581F', 'EAE8E99', '797E733', '6491025', 'D946DD7', 'BD97657', '957ADCE', 'D8350AC', '47C816F', 'FFBAC3E', '54FAA77', '3DC3512', '4FF7612', 'F6C2267', '6069160', '42AA5DA', '0BC2CB8', '91CDA53', '2EAF9B8', '9DB0A67', '81A4BA5', '2054C22', '35ADF05', '364503F', 'B032547', 'F74DA31', '8843F47', '625D65B', '9C4A366', '43BC631', 'D4C685A', '9EBB46F', '6C84150', 'D688434', '78C5386', 'E01E8AC', '6F05490', '37EC0B8', '83EF01D', 'B0A75C8', '19FDBE2', 'D7B189A', 'BDE4B4E', 'D26D296', '15DC47C', '63BCADE', 'AB9C6F8', '9D905AB', '62E5BFD', '7BC748F', 'F4A4459', 'BBEDC96', '60562AE', '0FC714F', '7F75911', '0809D31', 'ACB6CDC', '84C6E20', 'A0497EF', '593DE99', '0BCFDAD', 'F21F683', '76CDC1F', 'B962E80', '1821415', '8B12C97', '3ADFDE2', 'C64C50C', 'D2F43D1', 'C206C86', '93A73BD', '8608CF3', '043A04C', '14FA295', 'BE985F2', '0A581AE', '5D3C963', '4D59805', 'A82A2EB', '8C05D65', '2F78D7E', '9761ECE', 'CDDA99E', '3D77FB0', '7DF27B6', 'BB0264C', '08ECD83', '7D93CAD', 'A23979E', '28A0724', '9036B39', 'DCEF3B0', '84840AF', 'FACEF88', 'D905385', '4895752', 'CB0B606', '709D387', '8FA78CC', 'BF2DE67', '9446F48', '133A06F', '70F509B', '7A0CACA', '9F54016', 'AFBB8AA', '55DC7E7', '2BFD804', 'BCF9E89', 'D33EBFE', '36EE35D', '1BE32DA', '284881B', '3B79DC3', '28407D9', 'ECD257F', '3E6C79F', 'EDE02F2', '8A3A02C', 'D5835FC', 'A5F0ED4', '60023D8', '5A0B736', 'A1ECC3E', '9200C92', 'FFB3DD7', '85BFD59', '9294326', 'B975E12', '9CAB049', '29D313F', 'B668B4C', 'BE0E94C', '2F28F08', 'C8E9682', '8637F7B', 'A71F414', 'C01A4AE', '1E20E28', '2394FDB', '876271E', '30AF6A8', '814EA43', '819A28B', '2ECB618', '1DF6867', '001CB10', '4C6FA6A', '964743E', 'A097297', 'CA10F94', '7DDEC57', 'B907073', '7FBBD87', '0FD1B1D', '0CCC6D6', 'E43DE7C', '8073EC1', '11AAE6B', '59F5204', 'E958D76', '935E446', '2E53A19', '3358D76', 'A073096', '904A16B', '7B7D13D', 'CD963A9', '9F2179F', '2A4B818', 'D395212', 'C4F3A52', '157B174', '335D5C0', 'FF1D5E5', '1F5F5ED', '816F965', '87B3574', 'B0C91CC', 'ED7A3DA', '835592F', 'CFB084B', '9C95319', '6F75768', '9AF6220', 'AF779CA', '3B9EE3C', '61F996B', 'B7D4087', '4B2AFC8', 'A12DC80', 'F44A398', 'D9FFA62', 'F04432F', 'C320463', 'BBFAD37', 'A91F75F', 'DFF241E', 'A8EAF8F', '6E60A96', 'ED76217', '79AA692', 'ABB49AA', '2EAAAE0', 'FCBEBDE', '91D4AC2', '0C546F1', '5895724', 'A9CB72A', 'AE8DF89', '1BCAF31', '1BDC767', 'AB84654', 'EA7CC52', '215A278', 'D2200AE', 'FC55374', 'DD78B7C', 'F32A02C', 'A8E0CB8', '8A3293F', 'A53A16B', '1AA5080', '0CAE706', '6ADBFDB', 'D0A35C0', '304BBE5', 'C792948', '3EA0746', '4588C89', '89E7D7B', '485CD5E', '745E400', '5F1FC42', 'B8F6C78', '89E28A9', '23CED14', 'EBF2887', '8D8EF81', '475D5ED', '9D3FF60', '836E2E2', 'FB68B56', '249A26B', 'E4FF775', 'D234B1A', '094391E', '69C373D', '5C919E7', '0213C30', '165159F', '5BD9096', '4621610', '7D1F307', '94A33BE', '9113A77', 'D055A25', '9F07DD9', 'FA197FE', 'ECDFBA2', '0994EFE', 'BFD48B5', 'EF0B07C', 'FB1C352', 'C91D945', '8FA2AD6', 'B000FCD', 'F56999E', '397F99E', '1E9FC44', 'E7A789A', 'E71558D', 'CDC86E7', '3A92E61', '62E32AC', '10DB74A', '5F1AE6C', 'FB79825', 'F7EAFEF', '5C3C721', 'ECC31FD', '6819AAB', '678E24A', '7D2A7D2', '3F0451D', 'AAA92FF', '9B224AB', '88D5139', '8AD2CBD', '8AACF31', '25BEB53', '8A22FB0', 'E11CBDE', 'BC58420', '085D5C0', '2D37310', '2509DFC', '759DD53', '52839BD', 'D69E935', 'A9F41E6', 'CF128E2', '5727E96', 'FE0ACF6', '1BC2F09', 'C6DC614', '67BFE75', '1BF2BA6', 'BB6ABD1', 'AD5DA94', 'A7B8EBF', 'E4A440C', 'A9A6C52', 'E149892', 'E373C9C', '2F18EAB', 'B2AF6E0', '25E751B', '917A970', '4A8F4E8', '36E0512', '6A7B145', '66C44CC', '99BA9E4', '3CB1662', 'C2AC21C', '6ED4F8E', 'FD51A03', 'FA53B77', 'BD7C977', '5797365', 'CC7D11E', 'E8D2AB3', '0658A36', '1F4F9BD', '20D49E5', 'CAD18DC', '43C6109', '44C81FE', '9FE523D', 'CE07221', '0FB73C8', '306B36A', '108CCA5', 'DAECED6', '7BCA2FE', '4C545D0', '8699124', '13EBD14', '27393B7', '8A9E2DA', '331EE3F', 'DD4F5E4', '0057F36', '23C75C0', '1E3237E', 'F46EFCC', 'A01F0B8', '03A52E7', 'A6347C3', '40B8320', '325D020', 'E9650BF', '4944572', 'CAD2EBA', '975F39D', '28DC8BA', 'FE306A2', 'C67E710', '0DB208C', 'F84675F', 'D1A99C4', 'BC7C77A', '3184397', 'D673610', '9229A6D', '8363199', '7C57FC7', '1F879D8', 'F05288B', '9B4CE7D', '9F01CBE', '6A40A9C', 'C5F8436', '3D15633', '6FA7E45', '386CAC2', '9A4177E', '5850ECE', 'B8F376F', '0EFAFA1', 'C1FE43D', 'F213692', '352A93B', 'DD345A7', 'CAD94E0', '3250020', '96BB245', '9F09246', '3980A74', '3CBDA78', 'C5E3396', '5945B13', 'E5D59E7', '34ACF3A', 'FB870C8', 'F293E18', '3098BC4', 'FE9B141', '063146F', '6944116', '839F869', 'FE64C9F', '8EDDC14', '6618A27', 'FEC199E', '997CC20', '8CC2D46', 'AE6234D', 'E380DB9', 'B5D8E62', '4B34B3B', '6D69DBF', '9D41690', '90DE266', 'F92682C', 'D1EADDE', 'B649B0D', '5736467', 'FC44641', '955C4A8', 'BF73B18', '5692A32', '6985B3D', '3C5416C', '0ECBB58', '599323D', '153FAFD', '16084F1', 'F23B171', '72FEF6A', 'B075E1C', '7CC758E', '1025CC8', '01B1AB7', '80D6BC4', '5B9794B', '79C413E', 'EF4178F', 'CAAE951', '5400B84', 'D581FB4', 'EC03C5C', '13D186C', '30E3D13', '1F3231D', 'E7CDCB0', 'FEC0D6F', '43056CE', '87611B2', '4FF4D62', 'D392C37', 'DB4D05C', 'C34305F', 'B9275E9', '6262241', '69FAAB0', 'ED9D432', '8F3D349', '31F059B', '50BAB9E', '61DFFBB', '30642C5', '6590A5D', '6CE27EC', '013EA5A', 'AD7B3C3', '0CEEB77', '3DA46EF', '7964BF1', '0254A48', '78C083B', '4E68EDC', 'E4ECF42', '11A1C42', '4863CF9', '5C89E0E', 'D6108DC', 'B0D9A25', 'CB580FD', 'B46A120', '436E457', '85C4B27', '50FA8A5', '1A61530', '8073189', 'CCDADE7', 'C0CB0EC', 'F8BA7C2', 'FE902FC', '13297C9', '1ABA96C', 'F3C7C55', 'DF40CC4', '564381E', '6DB6D1B', '221D656', 'B125A57', 'B45DBA3', '49DA736', 'EC81876', '17A158D', 'B60A3BF', 'C853F2D', '3C9D1BD', 'C8494A6', 'BDE78B1', '31FAAEB', 'DE9A3D0', '585DC48', 'E0C4A8D', 'A7864E0', 'CCA29C3', 'B7A6AD2', '45C7B32', 'EE2C971', '48BE3F7', '481B467', 'D56EBBB', '08714A3', 'B0B7A90', 'E189302', 'DF3D40E', '47ABC39', '81DB023', '1C4B7F5', '2A2ED58', 'C008277', '97D4B9C', '72AB3DF', '853B301', 'E8C87AE', '122C80E', '54FFFDF', '74377B3', 'CEB27E1', 'EC402C1', 'B8569AB', '024607E', 'A138480', '10EF879', 'B0F1CE9', '46C6E9F', '8A1E2FC', 'CE26C1C', '8FC0551', '22BC8A0', '6335DA0', '8E55436', '1FD5016', '7C531F1', '27EEAEA', '06C1D85', '496B41F', 'D6B7233', '3585DBB', '022F01D', '8B7D739', 'F429EFD', 'D04B1EE', 'E260E4C', '531109A', 'F7F91B4', '46A14F9', '3723AA0', '8DB6CB6', '541D51B', '103C084', 'B6FD83D', '880E81A', '13BBD49', 'FE91B6E', 'C14FA02', '3673FEF', '148B090', '037D518', '38D5E93', 'B0A6BDC', '10F0059', 'D81D13A', 'E07EF6E', '70DE699', '9946D73', '95A443B', 'BD4492B', 'CCD4636', 'A21CABC', '1986C8D', 'BF0E5A3', 'D14299A', 'E054889', '23C06B5', 'F542D61', '2FA8250', '499CFDA', 'FB9CEBC', 'B533C35', '7F6F864', '8155BE8', '41021CD', '99B9D65', 'D6CE557', 'C4D1D16', '537F8D1', '206DC82', 'EC6CE1B', '379B121', 'E2AEC76', '27B894D', '1C4A80B', 'BF5357D', '6A7D5F6', 'BD99DEC', 'B07A56D', '184AE4B', '2FE96F0', 'DA57E67', '24C8D60', '76F52B9', '53B894C', '42A4324', '55E1ECD', '2B7601F', '1623473', 'BF329A8', 'C1A269D', '1635AA1', '0A60B3A', '4A9F7EC', 'BE3A11F', '0B16C0F', 'A1A0FA0', '62ED93B', 'E8A7F2E', '8C91656', '597B425', 'CA009A4', '9710FD0', '3EF1B8E', '10C9276', '5894229', '557F41B', 'A677A5D', '3B035AD', '449EA14', '3F5CB42', 'F1DF2DC', '5214C93', '8962422', '3C5E9C4', '8807F11', '9AB8333', '644D213', 'B545A3A', 'CD15620', 'BE0B505', '539220B', '56F7E49', '1A096AD', 'CD70539', '8DCE3E6', '7FC701A', '07088EC', '6AC0A4F', '677C124', 'A9206BD', '6E540DE', 'BB6CF36', '8800E6D', 'B606D1A', 'A513DCA', '26F3ABE', '0D3E284', '223C9A0', '25612A2', 'FBE0CF0', '784A86A', '8C306ED', '6F54498', '515C66F', 'BE278ED', 'C670761', '217F43B', '2FBC583', '4E3BC85', '32413D5', '429D320', '37EF0A9', '82B6C57', '19BD67B', '4CC7DE1', '615885A', 'CDB49F1', '4E2ABAB', '13EDECF', 'C6A9492', '456B05D', '554AA39', '32A40D6', '445B6E0', 'C14F8FB', '07E1BDA', '2BC270A', 'FDF058E', 'CC35006', '0BE1FE8', 'D6DAED6', '3C0166F', 'E13EA7D', 'A9E3DB6', '7660343', '2A222CD', 'E539F9C', '644F1EB', 'BB228E1', '68A8839', '4CCEDD5', 'E30E343', 'D30C664', '7A3FA0D', 'F7DE545', '584FAD8', '995D912', '283A359', '8D836CA', 'A657294', '3DF2E04', '6FE07FD', '76849A6', '4650CCD', '408B0FA', '340E753', '2E6800F', '3AC542E', 'D2B45E2', '14012FD', '09E597F', 'FDDEB61', 'ACCF347', '49206F6', 'D7ECCE3', '8123BE4', '2BB7F5F', '6174507', 'A22C806', 'D3B0756', '67F769B', '6C7F12B', '9A42E4E', '4D72F59', '002DAC3', '42D4EFE', 'E0F5CC0', 'EA8AA09', 'C35BE8F', '9325EA4', '1633CE7', '74BBA4F', 'AA69C45', 'B0D6B95', 'BB87553', '841BE7B', 'E726A50', 'D363BD3', '3BBBCE1', '1EB798B', 'FEB7BD6', '623E041', '4D50824', 'BB8442D', '2AF16CD', '1DEC4BC', '8F39919', '1167DD0', '1B992C3', '739BDCA', '91E8C22', '1120DA6', 'E9EF6A1', '4777B0A', '7FC5012', '42A5E09', 'A427970', '4C237F3', 'C9C0304', '06826D5', '18412D8', '09F2771', 'A4FAEAF', 'C945B3C', '7A7E808', 'EF41A48', '7BFC64A', '1F27E80', '5F12E4E', 'D1EBB32', 'BD3AA74', 'E3EA2CF', '11B5685', 'DC8628D', '3A3D995', '93F3BAA', '6E5813C', 'B7B3B2F', 'B46D194', '7683037', '04E0298', '0EFE357', '913FC97', 'A737AB2', '92F12EA', '4EC93C4', '88DD82D', '20E349F', 'BF0DA70', '18195D1', 'E4E46F1', 'BBF720B', 'CC95D9A', '37D3DED']  # pylint: disable=line-too-long


def _is_eligible_for_REV1074_experiment(request, sku):
    """
    For https://openedx.atlassian.net/browse/REV-1074 we are testing a mostly hardcoded version of the checkout page.
    We are trying to improve performance and measure if there is an effect on revenue.
    In order to improve performance and simplify the engineering work, many use cases are not being handled.
    These use cases will all need to be omitted from the experiment and sent to the regular checkout page
    """
    basket = request.basket
    user_agent = request.META.get('HTTP_USER_AGENT')
    omit = (
        # We applied filters to our list of courses and only some courses will be included in the experiment
        sku not in SKUS_IN_EXPERIMENT or
        # The static page doesn't support offers/coupons so baskets with either are omitted from the experiment
        basket.applied_offers() or
        basket.voucher_discounts or
        basket.total_discount or
        # Optimizely is being used by the mobile app on the checkout page.
        # We are removing optimizely from the static version of the page,
        # so we are omitting mobile app traffic from this experiment
        (user_agent and re.search(r'edX/org.edx.mobile', user_agent)) or
        # Bundles would add substantial additional complexity to the experiment so we are omitting bundles
        basket.num_items > 1 or
        # The static page only supports seat products
        not basket.lines.first().product.is_seat_product or
        # The static page is not supporting enterprise use cases so enterprise learners need to be excluded
        # Excluding all offers and coupons above should handle most enterprise use cases
        # This check should handle enterprise users
        # TODO: I don't think this check works yet
        getattr(request.basket, 'ENTERPRISE_CATALOG_ATTRIBUTE_TYPE', None) or
        # We do not want to include zero dollar purchases
        request.basket.total_incl_tax == 0 or
        str(request.user.username).startswith('test_') and str(request.user.email).endswith('example.com')
    )
    return not omit


def add_REV1074_information_to_url_if_eligible(redirect_url, request, sku):
    """
    For https://openedx.atlassian.net/browse/REV-1074 we are testing a mostly hardcoded version of the checkout page.
    We are trying to improve performance and measure if there is an effect on revenue.
    Here we determine which users are eligible to be in the experiment, then bucket the users
    into a treatment and control group, and send a log message to record this information for our experiment analysis
    """
    is_eligible_for_experiment = _is_eligible_for_REV1074_experiment(request, sku)
    bucket = stable_bucketing_hash_group('REV-1074', 2, request.user.username)
    route = bucket
    username = request.user.username
    basket = request.basket
    if not is_eligible_for_experiment:
        route = 0
        logger.info('REV1074: Should be omitted from experiment results: user [%s] with basket [%s].', username, basket)
    elif is_eligible_for_experiment and bucket:
        logger.info('REV1074: Bucketed into treatment variation: user [%s] with basket [%s].', username, basket)
    else:
        logger.info('REV1074: Bucketed into control variation: user [%s] with basket [%s].', username, basket)
    if route:
        redirect_url += sku + '.html'
    return redirect_url


def stable_bucketing_hash_group(group_name, group_count, username):
    """
    An implementation of a stable bucketing algorithm that can be used
    to reliably group users into experiments.

    Return the bucket that a user should be in for a given stable bucketing assignment.

    This function has been verified to return the same values as the stable bucketing
    functions in javascript and the master experiments table.

    Arguments:
        group_name: The name of the grouping/experiment.
        group_count: How many groups to bucket users into.
        username: The username of the user being bucketed.
    """
    hasher = hashlib.md5()
    hasher.update(group_name.encode('utf-8'))
    hasher.update(username.encode('utf-8'))
    hash_str = hasher.hexdigest()

    return int(re.sub('[8-9a-f]', '1', re.sub('[0-7]', '0', hash_str)), 2) % group_count
