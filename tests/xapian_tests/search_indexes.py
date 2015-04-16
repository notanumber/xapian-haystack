from haystack import indexes

from . import models


class DocumentIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True)
    summary = indexes.CharField(model_attr='summary')

    type_name = indexes.CharField(model_attr='type_name')

    number = indexes.IntegerField(model_attr='number')

    name = indexes.CharField(model_attr='name')
    date = indexes.DateField(model_attr='date')

    tags = indexes.MultiValueField()

    def get_model(self):
        return models.Document

    def prepare_tags(self, obj):
        l = [['tag', 'tag-test', 'tag-test-test'],
             ['tag', 'tag-test'],
             ['tag']]
        return l[obj.id % 3]
