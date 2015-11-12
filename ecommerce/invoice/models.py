from django.db import models


"""
Model to capture that an invoice was generated for a given order.
"""


class Invoice(models.Model):
    invoice_number = models.CharField(max_length=20)
    order_number = models.CharField(max_length=20)
    client = models.ForeignKey('core.Client')
    state = models.CharField(max_length=10, default='Not Paid', choices=[('Not Paid', 'Not Paid'), ('Paid', 'Paid')])
    created_at = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=19, decimal_places=2)
    purchase_order_number = models.CharField(max_length=20, blank=True)
