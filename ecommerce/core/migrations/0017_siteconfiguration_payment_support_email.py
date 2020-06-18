# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_siteconfiguration_enable_enrollment_codes'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='payment_support_email',
            field=models.CharField(default=b'support@example.com', help_text='Contact email for payment support issues.', max_length=255, verbose_name='Payment support email', blank=True),
        ),
    ]
