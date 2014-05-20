from haystack import indexes

from . import models


class DocumentIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True)
    summary = indexes.CharField(model_attr='summary')

    type_name = indexes.CharField(model_attr='type_name')

    number = indexes.IntegerField(model_attr='number')

    name = indexes.CharField(model_attr='name')
    date = indexes.DateField(model_attr='date')

    def get_model(self):
        return models.Document()
