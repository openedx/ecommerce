from hashlib import md5
def make_digital_book_sku(book_key,partner_id):
    _hash = ' '.join((
        unicode(book_key),
        unicode(partner_id)
    )).encode('utf-8')
 
    md5_hash = md5(_hash.lower())
    digest = md5_hash.hexdigest()[-7:]
    return digest.upper()


PARTNER_ID = 'cae1c9f5-f312-4ed7-8fce-729ba9b64244'
BOOK_KEY = 'digital-book-test-1'

print("sku: %s" % make_digital_book_sku(BOOK_KEY, PARTNER_ID))