from oscar.apps.dashboard.catalogue.forms import ProductForm as BaseProductForm


class ProductForm(BaseProductForm):
    class Meta(BaseProductForm.Meta):
        fields = [
            'title', 'course', 'expires', 'upc', 'description',
            'is_public', 'is_discountable', 'structure'
        ]
