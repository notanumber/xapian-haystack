from django.db import models


class Document(models.Model):
    type_name = models.CharField(max_length=50)
    number = models.IntegerField()
    name = models.CharField(max_length=200)

    date = models.DateField()

    summary = models.TextField()
    text = models.TextField()
