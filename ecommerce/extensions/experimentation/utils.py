"""
Experimentation utilities
"""

import hashlib
import logging
import re

from ecommerce.enterprise.utils import get_enterprise_id_for_user
from ecommerce.extensions.analytics.utils import track_segment_event

logger = logging.getLogger(__name__)

SKUS_IN_EXPERIMENT = ['8017833', '624BDAA', 'EE1CB04', 'BC6BBAA', '4A988C5', '144CDD8', 'E657925', '777FAF3', '143887B', '67582C9', '68A1E24', 'B3336CB', 'C6730F7', '20F47A4', '93FCF30', '4FE34FB', '29B1BA7', 'B83FD08', '656458A', '148E53C', 'B0247FA', '6B46BF1', 'F73864F', '213A29B', '0D99E30', 'AC0DA9B', '1EF0043', '7526CED', 'C696471', '224D9AD', 'D44B137', '963658E', '2AEFD99', 'E552FB9', 'FFFC863', 'CACE7AC', '7508520', '65B746A', 'B00FA09', '5BCCB48', '0F65B99', 'A9C4D26', '1F61A90', 'F8EB55F', '68FBFA6', '6CB91FD', 'FAEA42A', 'DAA531F', '7E79EDB', '9B132B8', '0770C0B', 'ACDB5B5', '7E2E11B', '482C0BB', '9DEC502', 'CEFEBDB', '1BEB39B', '089EAAB', 'FC3205B', '4DB4D37', '35F2C9C', 'E4CCAD3', '4214003', '4A559DF', 'FBF8569', '164475D', '91BA616', '8500D5F', 'E263050', '27EB505', 'AC66C3D', 'F03831A', '81FE29C', '9D44A40', 'C0140D5', '78D2930', 'F04F182', '6C3D195', '1126215', '4FEA4FB', '86B3E67', '89E6691', 'A807D13', 'D22FD32', '3CF3B24', 'FBACD26', 'CD3EE67', '0320C8D', 'DEC87C6', 'B6AB0A9', '01E493D', 'FE51C56', '7C77D03', 'A2DA8DF', '0B240BB', 'D6AE966', '4573945', '58B45E0', '2BBEE56', 'A95601F', '669146F', '009CA20', 'D41A251', '55CEE9A', '1ED3F94', '1B9EC41', '7589F32', 'B45F9A3', '122C8E1', '18AD676', '1E56B30', '5C5505B', 'BF4DCCD', 'D79166A', '42A5E57', '64AADB8', 'FC89C35', 'FF92E92', '9182378', '60BF3F4', 'A46923A', '54FA8FB', 'E26E321', 'DBF7BF3', '6B60EE8', '96A027C', 'BB9105D', '22BA892', '5068BB6', '89763D1', 'A472927', 'A4038BB', '64EAE78', '7B4A192', 'CA1DE0D', '949787E', 'F340A62', 'BBE3929', 'CB61699', 'BA19F44', '6A91F09', '1D510D4', 'D1784FC', 'A473633', '6D55AAD', '4BC3573', '5970B4E', '26A2598', '6607806', 'C0BD010', 'DBC4D64', '969A888', '0F0DA06', '02EA649', 'C8F2BBC', 'F65F7B9', 'D182352', 'F2CDF07', '345BFE3', '0EC3158', '4F80AAC', '21B09B8', '9BBBEDB', '174E20E', '19352C1', '297CE5D', 'CEAAD2F', '06EBD89', 'C6CCC27', 'FB220EB', '135F2CD', '1AAD448', '4B007F5', '00E6293', '0E651C0', '2044189', '4E954A8', '51A8136', '9655325', '8EEF03E', 'D4F47A0', '08A0731', '385BA02', 'F19DBD9', '9F72772', '077A19A', 'AF7CCE9', 'FCBF76B', 'D4211FD', 'FACE8A9', '4E4692F', 'BE103E5', 'F245C3C', 'C7CDD47', '8DE8B53', 'BE80AAF', '52BA096', '5C79AD4', 'E2FED0A', 'C3BCD75', 'C3198E9', 'F6585A6', '7373203', '609F7EE', '7DEF497', '430E6BD', '6480E06', 'AFB262F', '5C30778', '9E0691A', '2BA05C8', 'E869539', '08B177B', 'A466996', 'CB19D6E', '9797854', 'A78A555', '261ABF2', 'E332E87', 'F0E5571', 'F7737F9', '3C3F384', '68B477E', '3606BB9', '4B565D8', '68666B0', 'C22CB6B', '3E24166', 'E5521D8', 'B142574', 'CEB0CBB', '5698055', '3A28450', 'CD8FE5C', '1C3EDA6', 'C8F8003', '104F207', 'EB8B605', '0F34DBB', '0054AEA', '0BC4166', '5E44B4A', '2B9CDE8', '87D0CF2', '78F65E1', 'E03F47D', '8F821E5', 'C0116EF', '7EDE46E', '76DBBB7', 'EB5A83D', 'E3C02F2', 'EAE8E99', 'D946DD7', '68C01C3', '8ECD2D6', 'BD97657', '47C816F', 'FFBAC3E', '54FAA77', 'C138D6C', 'E8C5D72', '91E0A6E', '8E52D6A', '3DC3512', '4FF7612', 'F6C2267', '6069160', '42AA5DA', '0BC2CB8', '5E721A4', '9140A32', '91CDA53', '2F6F069', '2EAF9B8', '14B4E37', 'DC1BF67', '4C540E2', '863A263', '9DB0A67', '81A4BA5', '2054C22', '35ADF05', '364503F', 'B032547', 'F74DA31', '6C3CC73', '8843F47', '625D65B', '3B1CBE9', '24474CA', '43BC631', '9C4A366', 'D4C685A', '9EBB46F', '6C84150', 'D688434', 'DE132D2', 'F049669', 'E01E8AC', 'DD59C7A', 'A4F5425', '37EC0B8', '9742F9A', '3B59463', 'B0A75C8', '19FDBE2', 'D7B189A', 'BDE4B4E', 'D26D296', '77CE83B', '75ACB89', '15DC47C', '63BCADE', 'AB9C6F8', '8C9ACD9', '62E5BFD', '7BC748F', 'F4A4459', 'BBEDC96', '60562AE', '0FC714F', '0809D31', 'ACB6CDC', '593DE99', '0BCFDAD', 'F21F683', '1821415', '8B12C97', '3ADFDE2', '7A60405', '7B7C712', 'C64C50C', 'D2F43D1', 'C206C86', '93A73BD', '8608CF3', '086AE20', '043A04C', '14FA295', 'BE985F2', '0A581AE', '5D3C963', '4D59805', 'A82A2EB', '8C05D65', '2D30EED', '2F78D7E', '1AD04BA', '9761ECE', 'CDDA99E', '3D77FB0', '7DF27B6', 'B00C42F', 'BB0264C', '7D93CAD', 'A23979E', '28A0724', 'AFE78BE', '9036B39', 'DCEF3B0', 'BA7898E', '84840AF', '78309B0', 'FACEF88', 'D905385', '5D4A40C', 'C8F69A1', 'E42C760', '4895752', 'ED66B31', '69C1A6F', '3E8B5B3', 'C8572CC', '3F56F40', '74F02E4', 'CB0B606', 'CE28282', '2797662', '31D66BC', '709D387', '8FA78CC', '470F24D', 'DE3CF9C', '180CE63', 'BC8B977', '9446F48', 'DF6FB39', 'BF2DE67', '7809001', '4745E72', '133A06F', '0EBA449', '3117884', '70F509B', '7A0CACA', '07364E1', '7DF7B65', '9F54016', 'AFBB8AA', '55DC7E7', '2BFD804', 'BCF9E89', 'D33EBFE', '36EE35D', '3B79DC3', '284881B', '1BE32DA', '3E6C79F', 'ECD257F', '28407D9', 'EDE02F2', '8A3A02C', 'D5835FC', '5A0B736', '60023D8', 'A5F0ED4', 'A1ECC3E', '12BE943', '9200C92', '4F9B3A9', 'FFB3DD7', '9294326', '29D313F', 'B668B4C', 'BE0E94C', '2F28F08', 'C8E9682', '8637F7B', '9B7EEC3', '2F289D5', 'A71F414', 'C01A4AE', '1E20E28', '0FBEAD4', '14F3705', '644649C', '123ADCE', '2394FDB', '30AF6A8', '819A28B', '814EA43', '1DF6867', '2ECB618', '001CB10', '4C6FA6A', 'A097297', 'CA10F94', '7DDEC57', '7FBBD87', 'B907073', '0FD1B1D', '0CCC6D6', 'E43DE7C', '11AAE6B', '59F5204', '8073EC1', 'BA7A482', '935E446', '2E53A19', 'E958D76', 'A073096', '904A16B', '3358D76', '7B7D13D', '9F2179F', '2A4B818', 'D395212', 'CD963A9', 'C4F3A52', '335D5C0', 'FF1D5E5', '157B174', '87B3574', '1F5F5ED', '816F965', '4AB18FC', 'ED7A3DA', '835592F', 'B0C91CC', 'CFB084B', 'AF779CA', '3B9EE3C', '9C95319', '9AF6220', '6F75768', '7E387FD', '61F996B', 'B7D4087', '4B2AFC8', 'A12DC80', 'F44A398', 'D9FFA62', 'F04432F', 'C320463', 'BBFAD37', 'A91F75F', '64957B5', 'DFF241E', 'A8EAF8F', 'ED76217', '79AA692', 'FCBEBDE', '91D4AC2', '0C546F1', '1BCAF31', 'AE8DF89', 'AB84654', '1BDC767', 'EA7CC52', 'D2200AE', '215A278', 'FC55374', 'DD78B7C', 'A8E0CB8', 'F32A02C', '8A3293F', 'A53A16B', '1AA5080', '0CAE706', '6ADBFDB', 'D0A35C0', '304BBE5', 'C792948', '3EA0746', '4588C89', '485CD5E', '745E400', '5F1FC42', '89E28A9', 'B8F6C78', '23CED14', 'EBF2887', '8D8EF81', '9D3FF60', '836E2E2', 'FB68B56', 'CD41D93', '249A26B', 'E4FF775', '53B1212', 'C64D6B7', 'D234B1A', '094391E', '5C919E7', '0213C30', '165159F', '5BD9096', '4621610', '7D1F307', '94A33BE', '9113A77', '5421E81', '5DA45AF', 'D055A25', '8631DE3', 'FA197FE', '40015C1', 'BFD48B5', '8CEFD5F', 'FB1C352', '545AB5A', '68678F2', 'C91D945', '5C8DC52', 'AFD9E10', 'F8FECCF', 'DB2613D', '962CE2A', 'F56999E', '3179CD4', '1E9FC44', '397F99E', 'E7A789A', 'E78D3E2', '023408A', '3A92E61', 'FC47037', '7634F3B', '08FFD63', '62E32AC', '014219C', '2BD0206', 'D361B5A', '10DB74A', '5F1AE6C', 'DF31E3E', 'FB79825', 'AE50487', 'B1237CB', 'D837FDF', '6819AAB', '678E24A', '9F8C88F', 'A6D1AF4', '7D2A7D2', '3F0451D', 'AAA92FF', '88D5139', '8AD2CBD', 'B61357E', '8AACF31', '17B30DB', '25BEB53', '8A22FB0', 'E11CBDE', 'BC58420', '2D37310', '2509DFC', '759DD53', '52839BD', 'D69E935', 'A9F41E6', 'CF128E2', '1DD6B98', 'BA83B7D', '5727E93', 'FE0ACF6', '8569079', 'FF40580', '1BC2F09', '41ABAD2', 'BBD45C4', '35E8C81', 'C6DC614', '67BFE75', '1BF2BA6', '685EC3D', 'BB6ABD1', '61F5D78', '1D01C22', 'CC52A4F', 'D73488A', '550F234', '0C58F26', 'AD5DA94', 'A7B8EBF', 'E4A440C', 'A9A6C52', 'B15B5A9', 'BB67848', '2E140A3', 'D36FC66', '64EE07A', '99F6AEA', 'F293B3C', '6185CF8', 'AFFA43E', 'A7AA62D', 'CAE1C65', '44033AD', 'F4EA36A', '0ED14FF', 'E373C9C', '7D1D14E', '2F18EAB', 'B2AF6E0', 'DC8D182', 'D846C7B', '25E751B', '917A970', '4A8F4E8', '36E0512', '66C44CC', '6A7B145', '7B1C547', '99BA9E4', '3CB1662', 'C2AC21C', '6ED4F8E', 'B7C35C3', 'FD51A03', 'FA53B77', 'BD7C977', '5797365', 'CC7D11E', 'E8D2AB3', '463CDAF', 'FB1D1EF', '4A774D7', '2752DB8', '07CF9F0', 'E213596', '802E5B3', '7A88C9F', '0B67432', '05B653C', '1F4F9BD', '64D3DA5', '0658A36', '20D49E5', 'CAD18DC', '43C6109', '44C81FE', '9FE523D', 'CE07221', '0FB73C8', '306B36A', 'FE92E7D', '108CCA5', 'DAECED6', 'D4E297A', '7BCA2FE', '4C545D0', '0127791', '8699124', '13EBD14', '8A9E2DA', '27393B7', 'D63712D', '331EE3F', '3F1BC13', 'DD4F5E4', '4B7CFB6', '0057F36', '7B1D58D', '6184F0A', '9918F77', '23C75C0', '1E3237E', 'F46EFCC', 'A01F0B8', '03A52E7', 'A6347C3', '1638887', '56B54E7', '8117462', '500B1A0', '355AC3B', '7806104', '8785A97', '40B8320', '325D020', 'E57F4FB', '428C0A0', 'E9650BF', '4944572', 'CAD2EBA', '801A6C1', '975F39D', '28DC8BA', 'FE306A2', 'C67E710', 'C4EE80E', 'BAB7387', '0DB208C', 'F84675F', 'D1A99C4', 'BC7C77A', '3184397', 'CB88DC2', 'D673610', '9229A6D', '8363199', '7C57FC7', 'F05288B', 'C5F8436', '3D15633', '9B4CE7D', '9F01CBE', '6A40A9C', 'B3ED75C', '4374D10', '92919FD', '6FA7E45', '386CAC2', '9A4177E', 'B8F376F', '0EFAFA1', 'C1FE43D', 'B9DBF6B', '4083FC1', 'F213692', '420223B', '352A93B', 'DD345A7', 'CAD94E0', '5541708', 'D75C8FE', '4937CB5', 'A3C054C', '3DC497C', '7A9DB25', '3D0C83C', '5E211B6', '5F1C4E1', '3250020', 'C8F58E2', '96BB245', '9F09246', '3980A74', '3CBDA78', 'C5E3396', '5945B13', 'E5D59E7', 'F6FAEB5', 'F9193FA', '583A4B0', 'FBDFEC1', '42DCBE8', '34ACF3A', '3B3E134', 'BF3AF47', 'FB870C8', 'F293E18', '6F9C8C7', '576793D', 'E93476D', '3098BC4', '1510F64', '2C1A295', 'FE9B141', '063146F', '6944116', '839F869', 'FE64C9F', 'BE52AE2', '8EDDC14', '6618A27', 'FEC199E', '997CC20', '8CC2D46', 'AE6234D', 'E380DB9', 'B5D8E62', '4B34B3B', '6D69DBF', 'B89A348', '9D41690', '90DE266', '59E37C6', 'DA855A8', '1230932', '14B7D59', 'B02EDB7', 'F92682C', 'D1EADDE', 'B649B0D', '5736467', 'FC44641', '332A628', '955C4A8', 'BF73B18', '93281C9', '8420524', '785A2E4', 'DAB6106', 'FFE56C9', 'C99CC4C', 'A1BBA4B', 'ABAEBB6', '5692A32', '6985B3D', 'EF64F32', '3C5416C', 'A8D4C6D', 'C4C675F', '599323D', '153FAFD', '91DCE14', 'F23B171', '72FEF6A', 'B075E1C', '7CC758E', '1025CC8', '01B1AB7', '80D6BC4', '5B9794B', '79C413E', 'EF4178F', 'CAAE951', 'E16BDCB', '5400B84', 'EC03C5C', '13D186C', '30E3D13', '1F3231D', 'E7CDCB0', 'C3B74BB', 'EB515FB', '2CB97DB', 'DA5CBE4', '5C32300', '89C1010', '4AF518B', '32DFF42', 'C3F6FB5', 'DBCA745', '81C7B17', 'B183BE0', '37783EA', '2ED780E', 'F39DD02', 'CA0A284', '0BC08B1', '608B124', 'FEC0D6F', '43056CE', '87611B2', '4FF4D62', 'D392C37', 'DB4D05C', 'C34305F', '91C8416', '6262241', '164F272', '69FAAB0', 'ED9D432', '8F3D349', '31F059B', '50BAB9E', '61DFFBB', '1C82D42', '855F642', 'CCEBC60', '2C21056', '66879F2', 'C532DB0', '065A3EE', 'BF52047', '266622', '76EBCDC', '30642C5', '6590A5D', '6CE27EC', '194BC79', 'ED22396', '013EA5A', '2A43427', 'AD7B3C3', '0CEEB77', '3DA46EF', '65CD537', '6F5BE8C', 'B94A1A4', '80F4F0D', 'A77B895', '273FF49', '0254A48', '4E68EDC', '78C083B', '11A1C42', '4863CF9', 'E4ECF42', 'B0D9A25', 'D6108DC', '5C89E0E', '436E457', 'B46A120', 'CB580FD', '1A61530', '85C4B27', '50FA8A5', '8073189', 'DF3133C', 'CCDADE7', 'AC4D7D2', 'F8BA7C2', 'C0CB0EC', '9C78618', '13297C9', '1ABA96C', '7A3312A', 'F3C7C55', 'DF40CC4', '564381E', '6DB6D1B', '221D656', 'B125A57', 'B45DBA3', '9385176', '49DA736', 'DA067E0', 'B4FC753', 'EC81876', '17A158D', 'B60A3BF', 'C853F2D', 'C8494A6', 'BDE78B1', '31FAAEB', 'DE9A3D0', 'F88A3FD', '585DC48', 'E0C4A8D', 'A7864E0', 'CCA29C3', '10E8F93', '46833C9', 'B7A6AD2', '0231EB9', '45C7B32', 'C1F4645', '602FDBE', '8C4F26E', 'EE2C971', 'F2B7012', '684AF1E', '653BFAA', '48BE3F7', '4C52B1D', 'FFF9393', '5454894', '6F1122B', '481B467', 'D56EBBB', '08714A3', 'B0B7A90', 'E189302', 'DF3D40E', '47ABC39', 'A5B886C', '1C4B7F5', '81DB023', '2A2ED58', 'C008277', '0E51A99', '72AB3DF', '97D4B9C', '955F103', '853B301', 'E8C87AE', '122C80E', '7508824', '54FFFDF', 'CEB27E1', 'EC402C1', 'B8569AB', 'A138480', '10EF879', 'B0F1CE9', '46C6E9F', '2F4222F', '54F7B06', 'CE26C1C', '8FC0551', 'A33BCF7', '5A5A815', '2BA53C8', '6335DA0', '7D22545', '8E55436', '1FD5016', '792C19C', 'EB65398', 'FFB741C', '24A580D', '0D590AD', 'E5A2869', '00FD4DD', '7C531F1', '27EEAEA', '06C1D85', 'ECCB99F', 'EC5A7D0', '70AF721', '1C8BC93', 'A1EF59F', 'D8FBAF0', '73034AC', '496B41F', 'D6B7233', 'ADC3EFA', 'F0AB7D7', '022F01D', '04C5C50', '3585DBB', '8B7D739', 'F429EFD', 'B70F69E', 'D04B1EE', '531109A', 'E260E4C', '46A14F9', '53E4706', 'F7F91B4', '1CEF439', '9972254', 'CD544AF', '3723AA0', '270113F', '8DB6CB6', '0C883D7', '541D51B', '529839C', '103C084', 'B6FD83D', '880E81A', '13BBD49', 'FE91B6E', 'C14FA02', '3673FEF', '148B090', '037D518', '6F3DD59', '38D5E93', 'B0A6BDC', '10F0059', 'D81D13A', 'E07EF6E', '70DE699', 'E8963C0', 'BAEDA3F', '95A443B', 'BD4492B', '0103925', 'CCD4636', '3204E41', 'A21CABC', 'A043080', '1986C8D', 'BF0E5A3', 'D14299A', '48011E4', 'E054889', '2D552B6', '6ED68DC', 'A9FCE25', '23C06B5', 'F542D61', '2FA8250', '499CFDA', 'A70C5B0', 'B2114AD', '7F6F864', 'B533C35', '8155BE8', '99B9D65', '75AEFB6', '41021CD', 'C4D1D16', 'F964F3A', 'D6CE557', '537F8D1', '206DC82', 'EC6CE1B', '3D9CEAB', '379B121', 'E2AEC76', '27B894D', '1C4A80B', 'BF5357D', '6A7D5F6', 'BD99DEC', 'B07A56D', '184AE4B', '2FE96F0', 'DA57E67', '24C8D60', '11A2FD5', '76F52B9', 'AFFDB58', '53B894C', 'F05E225', '42A4324', '55E1ECD', '670F138', 'DDCF175', 'ECE55D6', 'E22B0A1', 'A60363C', 'B79C03E', '5FC4051', '77A37AE', '1623473', '2B7601F', 'BF329A8', 'E8049E3', '0E42F1B', '1635AA1', '0A60B3A', '4A9F7EC', 'AE38A85', 'BE3A11F', '0B16C0F', '899FC81', '62ED93B', 'E8A7F2E', '8C91656', '597B425', 'CA009A4', '8E7C34B', '9710FD0', '3EF1B8E', '10C9276', '4FE4664', '6C78CCD', '5894229', '557F41B', 'C544705', '3B035AD', 'A677A5D', '449EA14', 'CA238A9', 'F1DF2DC', '3F5CB42', '120969F', '8962422', 'DEF34A2', '3C5E9C4', '29E58F2', '8807F11', '522E301', '9AB8333', '644D213', '539220B', '56F7E49', '1A096AD', '3DA7F69', '61CA271', '7FC701A', '07088EC', '6AC0A4F', '677C124', 'A9206BD', '0C596F4', '4F14CBE', 'CB26F85', '8800E6D', 'D22B7B0', 'B606D1A', 'A513DCA', 'E46761F', 'CD7675A', '26F3ABE', '68C4825', '0D3E284', '223C9A0', 'FBE0CF0', '25612A2', '691536D', 'AD55826', '2394797', 'F1D26E8', '784A86A', '8C306ED', '515C66F', 'BE278ED', 'C670761', '217F43B', '825D9E4', 'C4DE0C8', '4BA48D3', '32413D5', '429D320', '37EF0A9', '82B6C57', 'B9F82E1', '19BD67B', '4CC7DE1', '615885A', 'CDB49F1', '4E2ABAB', 'C6A9492', '13EDECF', '554AA39', '456B05D', '32A40D6', '3741482', '445B6E0', '8966AB4', 'CB7E9AA', 'DC5D6E1', 'F12387E', 'E6D1097', 'C14F8FB', '9DB056F', '07E1BDA', '2BC270A', 'FDF058E', 'CC35006', '9CEE267', 'D6DAED6', '28FBEA0', 'D02C3BC', 'F65565F', '3C0166F', 'B7E4CDC', 'C5BD43B', '762C003', 'DE732B3', '328E2BB', 'FAF8901', 'E13EA7D', '2A222CD', 'E539F9C', '50CC03C', 'D065531', 'BB228E1', '170106E', '68A8839', '4CCEDD5', 'E30E343', 'D30C664', '7A3FA0D', 'F7DE545', '584FAD8', '995D912', '283A359', '8D836CA', 'A657294', '3DF2E04', '6FE07FD', '76849A6', '4650CCD', '408B0FA', '340E753', '2E6800F', '3AC542E', 'FD99212', 'BCDF041', 'D2B45E2', '14012FD', '09E597F', 'FDDEB61', 'ACCF347', '49206F6', 'D7ECCE3', '97326FF', '8123BE4', '290089B', '2BB7F5F', '022F56B', '6174507', '44D6CF1', 'A22C806', '6D6729A', 'D3B0756', 'DD64D92', '67F769B', '280179', '6C7F12B', '423B795', '69470A1', '9A42E4E', '4D72F59', '42D4EFE', 'C03B4E2', 'E0F5CC0', 'F477461', 'C35BE8F', '9325EA4', '1633CE7', '74BBA4F', '5EFA5B0', 'AA69C45', 'BB87553', '841BE7B', 'E726A50', 'D363BD3', '3BBBCE1', '1EB798B', 'FEB7BD6', '623E041', '4D50824', 'BB8442D', '2AF16CD', '31C5A6A', '1B992C3', '739BDCA', '91E8C22', '1120DA6', 'E9EF6A1', '4777B0A', '21DC38A', '7FC5012', '42A5E09', 'A427970', '4C237F3', 'C9C0304', '06826D5', '18412D8', '09F2771', 'A4FAEAF', 'EF41A48', '7BFC64A', '1F27E80', '5F12E4E', 'D1EBB32', 'BD3AA74', 'E3EA2CF', '11B5685', 'DC8628D', '93F3BAA', '6E5813C', 'B7B3B2F', '7683037', 'AD6F5D2', '04E0298', '3B1D9A0', '0EFE357', '913FC97', 'A737AB2', '92F12EA', '4EC93C4', '88DD82D', '20E349F', 'BF0DA70', '18195D1', 'A0616C0', 'E4E46F1', 'BBF720B', 'CC95D9A', '37D3DED', '63DC4F3', 'EE38655', '8E957A1', '55C4D9B', '0E8E87F', 'DC79938', '705319F', 'E61BD8C', '012B863', '16D62C5', '2B21ABC', '00772E2', 'DEF4F97', '8C5B057', 'A264C6D', '003E11D', 'B093865', 'FCA0184', 'CC4617A', '56CA7E6', '9D36D42', 'FE0C255', '7D80415', '32C37C1', 'F1C4883', '229F201', '0CBCBDB', 'C9B1694', 'FB2BDF5', 'C937136', 'FD538FC', '4337172', 'A1FDDB9', '35CC4DE', 'E9388DA', 'E1002F7', 'CB921FD', 'ECA8D21', '631AA60', '430D6D5', 'DD69567', '994C99C', 'E691EA0', 'EC02DBD', '07503F4', 'C1C797D', '51B75B6', '9355CB3', 'A3134F2', 'BE5D7E3', '94F0BBF', '3602FB8', '016EEDB', '0A234DC', '1505C52', '087D332', '0A8DD10', 'EF94CEA', '780D368', 'D9B25F4', '3EE28DF']  # pylint: disable=line-too-long


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
        getattr(request.basket, 'ENTERPRISE_CATALOG_ATTRIBUTE_TYPE', None) or
        get_enterprise_id_for_user(basket.site, basket.owner) or
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
    properties = {
        'experiment': 'static_checkout_page',
        'cart_id': basket.id
    }
    if not is_eligible_for_experiment:
        route = 0
        logger.info('REV1074: Should be omitted from experiment results: user [%s] with basket [%s].', username, basket)
        properties['bucket'] = 'not_in_experiment'
    elif is_eligible_for_experiment and bucket:
        logger.info('REV1074: Bucketed into treatment variation: user [%s] with basket [%s].', username, basket)
        properties['bucket'] = 'treatment'
    else:
        logger.info('REV1074: Bucketed into control variation: user [%s] with basket [%s].', username, basket)
        properties['bucket'] = 'control'

    track_segment_event(request.site, request.user, 'edx.bi.experiment.user.bucketed', properties)

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
