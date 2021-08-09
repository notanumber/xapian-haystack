from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '__first__'),
        ('contenttypes', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_name', models.CharField(max_length=50)),
                ('number', models.IntegerField()),
                ('name', models.CharField(max_length=200)),
                ('date', models.DateField()),
                ('summary', models.TextField()),
                ('text', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='DjangoContentType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ],
        ),
        migrations.CreateModel(
            name='BlogEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datetime', models.DateTimeField()),
                ('date', models.DateField()),
                ('author', models.CharField(max_length=255)),
                ('text', models.TextField()),
                ('funny_text', models.TextField()),
                ('non_ascii', models.TextField()),
                ('url', models.URLField()),
                ('boolean', models.BooleanField()),
                ('number', models.IntegerField()),
                ('float_number', models.FloatField()),
                ('decimal_number', models.DecimalField(decimal_places=2, max_digits=4)),
                ('tags', models.ManyToManyField(to='core.MockTag')),
            ],
        ),
    ]
