from django.db import models
from django.contrib.contenttypes.models import ContentType

from ..core.models import MockTag, AnotherMockModel, MockModel, AFourthMockModel


class Document(models.Model):
    type_name = models.CharField(max_length=50)
    number = models.IntegerField()
    name = models.CharField(max_length=200)

    date = models.DateField()

    summary = models.TextField()
    text = models.TextField()


class AbstractBlogEntry(models.Model):
    """
    Same as tests.core.MockModel with a few extra fields for testing various
    sorting and ordering criteria.
    """
    datetime = models.DateTimeField()
    date = models.DateField()

    tags = models.ManyToManyField(MockTag)

    author = models.CharField(max_length=255)
    text = models.TextField()
    funny_text = models.TextField()
    non_ascii = models.TextField()
    url = models.URLField()

    boolean = models.BooleanField()
    number = models.IntegerField()
    float_number = models.FloatField()
    decimal_number = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        abstract = True


class BlogEntry(AbstractBlogEntry):
    pass


class UUIDBlogEntry(AbstractBlogEntry):
    """
    A blog entry with string based primary key instead of an integer.
    Covers #138
    """
    uuid = models.CharField(primary_key=True, max_length=20)


class DjangoContentType(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
