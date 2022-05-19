from oscar.apps.dashboard.catalogue.forms import StockRecordForm as BaseStockRecordForm


class StockRecordForm(BaseStockRecordForm):

    class Meta(BaseStockRecordForm.Meta):
        fields = [
            'partner', 'partner_sku',
            'price_currency', 'price_excl_tax', 'price_retail', 'cost_price',
            'num_in_stock', 'low_stock_threshold', 'android_sku', 'ios_sku'
        ]
