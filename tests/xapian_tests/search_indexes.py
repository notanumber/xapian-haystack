from __future__ import unicode_literals

from haystack import indexes

from . import models


class DocumentIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True)
    summary = indexes.CharField(model_attr="summary")

    type_name = indexes.CharField(model_attr="type_name")

    number = indexes.IntegerField(model_attr="number")

    name = indexes.CharField(model_attr="name")
    date = indexes.DateField(model_attr="date")

    tags = indexes.MultiValueField()

    def get_model(self):
        return models.Document

    def prepare_tags(self, obj):
        lst = [["tag", "tag-test", "tag-test-test"], ["tag", "tag-test"], ["tag"]]
        return lst[obj.id % 3]


class BlogSearchIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True, use_template=True, template_name="search/indexes/core/mockmodel_text.txt",)
    name = indexes.CharField(model_attr="author", faceted=True)
    date = indexes.DateField(model_attr="date")
    datetime = indexes.DateField(model_attr="datetime")
    number = indexes.IntegerField(model_attr="number")
    boolean = indexes.BooleanField(model_attr="boolean")
    # slug = indexes.CharField(indexed=False, model_attr="slug")
    float_number = indexes.FloatField(model_attr="float_number")
    month = indexes.CharField(indexed=False)
    url = indexes.CharField(model_attr="url")
    empty = indexes.CharField()

    # Various MultiValueFields
    sites = indexes.MultiValueField()
    tags = indexes.MultiValueField()
    keys = indexes.MultiValueField()
    titles = indexes.MultiValueField()

    def get_model(self):
        return models.BlogEntry

    def prepare_sites(self, obj):
        return ["%d" % (i * obj.id) for i in range(1, 4)]

    def prepare_tags(self, obj):
        if obj.id == 1:
            return ["a", "b", "c"]
        elif obj.id == 2:
            return ["ab", "bc", "cd"]
        else:
            return ["an", "to", "or"]

    def prepare_keys(self, obj):
        return [i * obj.id for i in range(1, 4)]

    def prepare_titles(self, obj):
        if obj.id == 1:
            return ["object one title one", "object one title two"]
        elif obj.id == 2:
            return ["object two title one", "object two title two"]
        else:
            return ["object three title one", "object three title two"]

    def prepare_month(self, obj):
        return "%02d" % obj.date.month

    def prepare_empty(self, obj):
        return ""


class CompleteBlogEntryIndex(indexes.SearchIndex):
    text = indexes.CharField(model_attr="text", document=True)
    author = indexes.CharField(model_attr="author")
    url = indexes.CharField(model_attr="url")
    non_ascii = indexes.CharField(model_attr="non_ascii")
    funny_text = indexes.CharField(model_attr="funny_text")

    datetime = indexes.DateTimeField(model_attr="datetime")
    date = indexes.DateField(model_attr="date")

    boolean = indexes.BooleanField(model_attr="boolean")
    number = indexes.IntegerField(model_attr="number")
    float_number = indexes.FloatField(model_attr="float_number")
    decimal_number = indexes.DecimalField(model_attr="decimal_number")

    multi_value = indexes.MultiValueField()

    def get_model(self):
        return models.BlogEntry

    def prepare_multi_value(self, obj):
        return [tag.name for tag in obj.tags.all()]


class XapianNGramIndex(indexes.SearchIndex):
    text = indexes.CharField(model_attr="author", document=True)
    ngram = indexes.NgramField(model_attr="author")

    def get_model(self):
        return models.BlogEntry


class XapianEdgeNGramIndex(indexes.SearchIndex):
    text = indexes.CharField(model_attr="author", document=True)
    edge_ngram = indexes.EdgeNgramField(model_attr="author")

    def get_model(self):
        return models.BlogEntry


class DjangoContentTypeIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True)

    def get_model(self):
        return models.DjangoContentType


class MockSearchIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True, use_template=True)
    name = indexes.CharField(model_attr="author", faceted=True)
    pub_date = indexes.DateTimeField(model_attr="pub_date")
    title = indexes.CharField()

    def get_model(self):
        return models.MockModel


class BoostMockSearchIndex(indexes.SearchIndex):
    text = indexes.CharField(
        document=True, use_template=True, template_name="search/indexes/core/mockmodel_template.txt",
    )
    author = indexes.CharField(model_attr="author", weight=2.0)
    editor = indexes.CharField(model_attr="editor")
    pub_date = indexes.DateField(model_attr="pub_date")

    def get_model(self):
        return models.AFourthMockModel


class MockQueryIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True)
    pub_date = indexes.DateTimeField()
    title = indexes.CharField()
    foo = indexes.CharField()

    def get_model(self):
        return models.MockModel
