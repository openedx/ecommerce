# -*- coding: utf-8 -*-


import django.db.models.deletion
import oscar.models.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0001_initial'),
        ('courses', '0001_initial'),
        ('catalogue', '0003_product_course'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalProduct',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('structure', models.CharField(default=b'standalone', max_length=10, verbose_name='Product structure', choices=[(b'standalone', 'Stand-alone product'), (b'parent', 'Parent product'), (b'child', 'Child product')])),
                ('upc', oscar.models.fields.NullCharField(max_length=64, help_text='Universal Product Code (UPC) is an identifier for a product which is not specific to a particular  supplier. Eg an ISBN for a book.', verbose_name='UPC', db_index=True)),
                ('title', models.CharField(max_length=255, verbose_name='Title', blank=True)),
                ('slug', models.SlugField(max_length=255, verbose_name='Slug')),
                ('description', models.TextField(verbose_name='Description', blank=True)),
                ('rating', models.FloatField(verbose_name='Rating', null=True, editable=False)),
                ('date_created', models.DateTimeField(verbose_name='Date created', editable=False, blank=True)),
                ('date_updated', models.DateTimeField(verbose_name='Date updated', db_index=True, editable=False, blank=True)),
                ('is_discountable', models.BooleanField(default=True, help_text='This flag indicates if this product can be used in an offer or not', verbose_name='Is discountable?')),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('changed_by', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to=settings.AUTH_USER_MODEL, null=True)),
                ('course', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='courses.Course', null=True)),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
                ('parent', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='catalogue.Product', null=True)),
                ('product_class', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='catalogue.ProductClass', null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical Product',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='HistoricalProductAttributeValue',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('value_text', models.TextField(null=True, verbose_name='Text', blank=True)),
                ('value_integer', models.IntegerField(null=True, verbose_name='Integer', blank=True)),
                ('value_boolean', models.NullBooleanField(verbose_name='Boolean')),
                ('value_float', models.FloatField(null=True, verbose_name='Float', blank=True)),
                ('value_richtext', models.TextField(null=True, verbose_name='Richtext', blank=True)),
                ('value_date', models.DateField(null=True, verbose_name='Date', blank=True)),
                ('value_file', models.TextField(max_length=255, null=True, blank=True)),
                ('value_image', models.TextField(max_length=255, null=True, blank=True)),
                ('entity_object_id', models.PositiveIntegerField(null=True, editable=False, blank=True)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('attribute', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='catalogue.ProductAttribute', null=True)),
                ('changed_by', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to=settings.AUTH_USER_MODEL, null=True)),
                ('entity_content_type', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='contenttypes.ContentType', null=True)),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
                ('product', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='catalogue.Product', null=True)),
                ('value_option', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='catalogue.AttributeOption', null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical Product attribute value',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='product',
            name='changed_by',
            field=models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='productattributevalue',
            name='changed_by',
            field=models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
