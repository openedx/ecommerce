# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import oscar.models.fields.autoslugfield
import oscar.core.validators
import oscar.models.fields
import django.db.models.deletion
from django.conf import settings
import django.core.validators


# Functions from the following migrations need manual copying.
# Move them and any dependencies into this file, then update the
# RunPython operations to refer to the local versions:
# ecommerce.extensions.catalogue.migrations.0002_auto_20150223_1052
# ecommerce.extensions.catalogue.migrations.0009_credit_hours_attr
# ecommerce.extensions.catalogue.migrations.0006_credit_provider_attr

def initialize_catalog(apps, schema_editor):
    """
    Create all the Product Types, Products, Attributes, Categories, and other data models we need out of the
    box for the EdX Catalog. This data migration will create the "Seat" type, along with our
    default product, a DemoX Course and Seat with an Honor Certificate.
    """
    Category = apps.get_model("catalogue", "Category")
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    # Create a new product class for course seats
    seat = ProductClass.objects.create(
        track_stock=False,
        requires_shipping=False,
        name='Seat',
        slug='seat'
    )

    attributes = (
        ('course_key', 'text', True),
        ('id_verification_required', 'boolean', False),
        ('certificate_type', 'text', False),
        ('credit_provider', 'text', False),
        ('credit_hours', 'integer', False),
    )

    for name, value_type, required in attributes:
        ProductAttribute.objects.create(
            product_class=seat,
            name=name,
            code=name,
            type=value_type,
            required=required
        )

    # Create a category for course seats
    Category.objects.create(
        description="All course seats",
        numchild=1,
        slug="seats",
        depth=1,
        path="0001",
        image="",
        name="Seats"
    )

class Migration(migrations.Migration):

    replaces = [(b'catalogue', '0001_initial'), (b'catalogue', '0002_auto_20150223_1052'), (b'catalogue', '0003_product_course'), (b'catalogue', '0004_auto_20150609_0129'), (b'catalogue', '0005_auto_20150610_1355'), (b'catalogue', '0006_credit_provider_attr'), (b'catalogue', '0007_auto_20150709_1205'), (b'catalogue', '0008_auto_20150709_1254'), (b'catalogue', '0009_credit_hours_attr')]

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0001_initial'),
        ('courses', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AttributeOption',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('option', models.CharField(max_length=255, verbose_name='Option')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Attribute option',
                'verbose_name_plural': 'Attribute options',
            },
        ),
        migrations.CreateModel(
            name='AttributeOptionGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, verbose_name='Name')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Attribute option group',
                'verbose_name_plural': 'Attribute option groups',
            },
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('path', models.CharField(unique=True, max_length=255)),
                ('depth', models.PositiveIntegerField()),
                ('numchild', models.PositiveIntegerField(default=0)),
                ('name', models.CharField(max_length=255, verbose_name='Name', db_index=True)),
                ('description', models.TextField(verbose_name='Description', blank=True)),
                ('image', models.ImageField(max_length=255, upload_to='categories', null=True, verbose_name='Image', blank=True)),
                ('slug', models.SlugField(verbose_name='Slug', max_length=255)),
            ],
            options={
                'ordering': ['path'],
                'abstract': False,
                'verbose_name': 'Category',
                'verbose_name_plural': 'Categories',
            },
        ),
        migrations.CreateModel(
            name='Option',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, verbose_name='Name')),
                ('code', oscar.models.fields.autoslugfield.AutoSlugField(populate_from='name', editable=False, max_length=128, blank=True, unique=True, verbose_name='Code')),
                ('type', models.CharField(default='Required', max_length=128, verbose_name='Status', choices=[('Required', 'Required - a value for this option must be specified'), ('Optional', 'Optional - a value for this option can be omitted')])),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Option',
                'verbose_name_plural': 'Options',
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('structure', models.CharField(default='standalone', max_length=10, verbose_name='Product structure', choices=[('standalone', 'Stand-alone product'), ('parent', 'Parent product'), ('child', 'Child product')])),
                ('upc', oscar.models.fields.NullCharField(max_length=64, help_text='Universal Product Code (UPC) is an identifier for a product which is not specific to a particular  supplier. Eg an ISBN for a book.', unique=True, verbose_name='UPC')),
                ('title', models.CharField(max_length=255, verbose_name='Title', blank=True)),
                ('slug', models.SlugField(max_length=255, verbose_name='Slug')),
                ('description', models.TextField(verbose_name='Description', blank=True)),
                ('rating', models.FloatField(verbose_name='Rating', null=True, editable=False)),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='Date created')),
                ('date_updated', models.DateTimeField(auto_now=True, verbose_name='Date updated', db_index=True)),
                ('is_discountable', models.BooleanField(default=True, help_text='This flag indicates if this product can be used in an offer or not', verbose_name='Is discountable?')),
                ('expires', models.DateTimeField(help_text='Last date/time on which this product can be purchased.', null=True, blank=True)),
                ('course', models.ForeignKey(related_name='products', blank=True, to='courses.Course', null=True)),
            ],
            options={
                'ordering': ['-date_created'],
                'abstract': False,
                'verbose_name': 'Product',
                'verbose_name_plural': 'Products',
            },
        ),
        migrations.CreateModel(
            name='ProductAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, verbose_name='Name')),
                ('code', models.SlugField(max_length=128, verbose_name='Code', validators=[django.core.validators.RegexValidator(regex=b'^[a-zA-Z_][0-9a-zA-Z_]*$', message="Code can only contain the letters a-z, A-Z, digits, and underscores, and can't start with a digit"), oscar.core.validators.non_python_keyword])),
                ('type', models.CharField(default='text', max_length=20, verbose_name='Type', choices=[('text', 'Text'), ('integer', 'Integer'), ('boolean', 'True / False'), ('float', 'Float'), ('richtext', 'Rich Text'), ('date', 'Date'), ('option', 'Option'), ('entity', 'Entity'), ('file', 'File'), ('image', 'Image')])),
                ('required', models.BooleanField(default=False, verbose_name='Required')),
                ('option_group', models.ForeignKey(blank=True, to='catalogue.AttributeOptionGroup', help_text='Select an option group if using type "Option"', null=True, verbose_name='Option Group')),
            ],
            options={
                'ordering': ['code'],
                'abstract': False,
                'verbose_name': 'Product attribute',
                'verbose_name_plural': 'Product attributes',
            },
        ),
        migrations.CreateModel(
            name='ProductAttributeValue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('value_text', models.TextField(null=True, verbose_name='Text', blank=True)),
                ('value_integer', models.IntegerField(null=True, verbose_name='Integer', blank=True)),
                ('value_boolean', models.NullBooleanField(verbose_name='Boolean')),
                ('value_float', models.FloatField(null=True, verbose_name='Float', blank=True)),
                ('value_richtext', models.TextField(null=True, verbose_name='Richtext', blank=True)),
                ('value_date', models.DateField(null=True, verbose_name='Date', blank=True)),
                ('value_file', models.FileField(max_length=255, null=True, upload_to='images/products/%Y/%m/', blank=True)),
                ('value_image', models.ImageField(max_length=255, null=True, upload_to='images/products/%Y/%m/', blank=True)),
                ('entity_object_id', models.PositiveIntegerField(null=True, editable=False, blank=True)),
                ('attribute', models.ForeignKey(verbose_name='Attribute', to='catalogue.ProductAttribute')),
                ('entity_content_type', models.ForeignKey(blank=True, editable=False, to='contenttypes.ContentType', null=True)),
                ('product', models.ForeignKey(related_name='attribute_values', verbose_name='Product', to='catalogue.Product')),
                ('value_option', models.ForeignKey(verbose_name='Value option', blank=True, to='catalogue.AttributeOption', null=True)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Product attribute value',
                'verbose_name_plural': 'Product attribute values',
            },
        ),
        migrations.CreateModel(
            name='ProductCategory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('category', models.ForeignKey(verbose_name='Category', to='catalogue.Category')),
                ('product', models.ForeignKey(verbose_name='Product', to='catalogue.Product')),
            ],
            options={
                'ordering': ['product', 'category'],
                'abstract': False,
                'verbose_name': 'Product category',
                'verbose_name_plural': 'Product categories',
            },
        ),
        migrations.CreateModel(
            name='ProductClass',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, verbose_name='Name')),
                ('slug', oscar.models.fields.autoslugfield.AutoSlugField(populate_from='name', editable=False, max_length=128, blank=True, unique=True, verbose_name='Slug')),
                ('requires_shipping', models.BooleanField(default=True, verbose_name='Requires shipping?')),
                ('track_stock', models.BooleanField(default=True, verbose_name='Track stock levels?')),
                ('options', models.ManyToManyField(to=b'catalogue.Option', verbose_name='Options', blank=True)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
                'verbose_name': 'Product class',
                'verbose_name_plural': 'Product classes',
            },
        ),
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('original', models.ImageField(upload_to='images/products/%Y/%m/', max_length=255, verbose_name='Original')),
                ('caption', models.CharField(max_length=200, verbose_name='Caption', blank=True)),
                ('display_order', models.PositiveIntegerField(default=0, help_text='An image with a display order of zero will be the primary image for a product', verbose_name='Display order')),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='Date created')),
                ('product', models.ForeignKey(related_name='images', verbose_name='Product', to='catalogue.Product')),
            ],
            options={
                'ordering': ['display_order'],
                'abstract': False,
                'verbose_name': 'Product image',
                'verbose_name_plural': 'Product images',
            },
        ),
        migrations.CreateModel(
            name='ProductRecommendation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('ranking', models.PositiveSmallIntegerField(default=0, help_text='Determines order of the products. A product with a higher value will appear before one with a lower ranking.', verbose_name='Ranking')),
                ('primary', models.ForeignKey(related_name='primary_recommendations', verbose_name='Primary product', to='catalogue.Product')),
                ('recommendation', models.ForeignKey(verbose_name='Recommended product', to='catalogue.Product')),
            ],
            options={
                'ordering': ['primary', '-ranking'],
                'abstract': False,
                'verbose_name': 'Product recommendation',
                'verbose_name_plural': 'Product recomendations',
            },
        ),
        migrations.AlterUniqueTogether(
            name='productrecommendation',
            unique_together=set([('primary', 'recommendation')]),
        ),
        migrations.AlterUniqueTogether(
            name='productimage',
            unique_together=set([('product', 'display_order')]),
        ),
        migrations.AlterUniqueTogether(
            name='productcategory',
            unique_together=set([('product', 'category')]),
        ),
        migrations.AlterUniqueTogether(
            name='productattributevalue',
            unique_together=set([('attribute', 'product')]),
        ),
        migrations.AddField(
            model_name='productattribute',
            name='product_class',
            field=models.ForeignKey(related_name='attributes', verbose_name='Product type', blank=True, to='catalogue.ProductClass', null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='attributes',
            field=models.ManyToManyField(help_text='A product attribute is something that this product may have, such as a size, as specified by its class', to=b'catalogue.ProductAttribute', verbose_name='Attributes', through='catalogue.ProductAttributeValue'),
        ),
        migrations.AddField(
            model_name='product',
            name='categories',
            field=models.ManyToManyField(to=b'catalogue.Category', verbose_name='Categories', through='catalogue.ProductCategory'),
        ),
        migrations.AddField(
            model_name='product',
            name='parent',
            field=models.ForeignKey(related_name='children', blank=True, to='catalogue.Product', help_text="Only choose a parent product if you're creating a child product.  For example if this is a size 4 of a particular t-shirt.  Leave blank if this is a stand-alone product (i.e. there is only one version of this product).", null=True, verbose_name='Parent product'),
        ),
        migrations.AddField(
            model_name='product',
            name='product_class',
            field=models.ForeignKey(related_name='products', on_delete=django.db.models.deletion.PROTECT, verbose_name='Product type', to='catalogue.ProductClass', help_text='Choose what type of product this is', null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='product_options',
            field=models.ManyToManyField(help_text="Options are values that can be associated with a item when it is added to a customer's basket.  This could be something like a personalised message to be printed on a T-shirt.", to=b'catalogue.Option', verbose_name='Product options', blank=True),
        ),
        migrations.AddField(
            model_name='product',
            name='recommended_products',
            field=models.ManyToManyField(help_text='These are products that are recommended to accompany the main product.', to=b'catalogue.Product', verbose_name='Recommended products', through='catalogue.ProductRecommendation', blank=True),
        ),
        migrations.AddField(
            model_name='attributeoption',
            name='group',
            field=models.ForeignKey(related_name='options', verbose_name='Group', to='catalogue.AttributeOptionGroup'),
        ),
        migrations.RunPython(code=initialize_catalog),
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
                ('expires', models.DateTimeField(help_text='Last date/time on which this product can be purchased.', null=True, blank=True)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('course', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='courses.Course', null=True)),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
                ('parent', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='catalogue.Product', null=True)),
                ('product_class', models.ForeignKey(related_name='products', on_delete=django.db.models.deletion.PROTECT, blank=True, to='catalogue.ProductClass', help_text='Choose what type of product this is', null=True, verbose_name='Product type')),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical Product',
            },
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
        )
    ]
