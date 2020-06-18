# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0001_initial'),
        ('catalogue', '0002_auto_20150223_1052'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='course',
            field=models.ForeignKey(related_name='products', blank=True, to='courses.Course', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
