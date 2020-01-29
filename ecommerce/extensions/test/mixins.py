class BenefitTestMixin:
    factory_class = None
    name_format = ''

    def setUp(self):
        super(BenefitTestMixin, self).setUp()
        self.benefit = self.factory_class()  # pylint: disable=not-callable

    def test_name(self):
        self.assertEqual(self.benefit.name, self.name_format.format(value=self.benefit.value))

    def test_description(self):
        self.assertEqual(self.benefit.description, self.name_format.format(value=self.benefit.value))
