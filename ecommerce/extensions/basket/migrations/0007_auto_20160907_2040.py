# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('basket', '0006_basket_site'),
    ]

    operations = [
        migrations.CreateModel(
            name='BasketAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('value_text', models.TextField(verbose_name='Text Attribute')),
            ],
        ),
        migrations.CreateModel(
            name='BasketAttributeType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=128, verbose_name='Name')),
            ],
        ),
        migrations.AddField(
            model_name='basketattribute',
            name='attribute_type',
            field=models.ForeignKey(verbose_name='Attribute Type', to='basket.BasketAttributeType', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='basketattribute',
            name='basket',
            field=models.ForeignKey(verbose_name='Basket', to='basket.Basket', on_delete=models.CASCADE),
        ),
        migrations.AlterUniqueTogether(
            name='basketattribute',
            unique_together=set([('basket', 'attribute_type')]),
        ),
    ]
