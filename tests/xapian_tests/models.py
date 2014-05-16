from django.db import models


class Document(models.Model):
    type_name = models.CharField(max_length=50)
    number = models.IntegerField()

    date = models.DateField()

    summary = models.TextField()
    text = models.TextField()
