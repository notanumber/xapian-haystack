import datetime
import cPickle as pickle
import os
import re
import warnings

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.encoding import smart_unicode, force_unicode

from haystack.backends import BaseSearchBackend, BaseSearchQuery
from haystack.exceptions import MissingDependency
from haystack.models import SearchResult

try:
    import xapian
except ImportError:
    raise MissingDependency("The 'xapian' backend requires the installation of 'xapian'. Please refer to the documentation.")


RESERVED_WORDS = (
    'AND',
    'NOT',
    'OR',
    'XOR',
    'NEAR',
    'ADJ',
)

RESERVED_CHARACTERS = (
    '\\', '+', '-', '&&', '||', '!', '(', ')', '{', '}', 
    '[', ']', '^', '"', '~', '*', '?', ':',
)

DATETIME_REGEX = re.compile('^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})T(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(\.\d{3,6}Z?)?$')

DEFAULT_MAX_RESULTS = 100000

DOCUMENT_ID_TERM_PREFIX = 'Q'
DOCUMENT_CUSTOM_TERM_PREFIX = 'X'
DOCUMENT_CT_TERM_PREFIX = DOCUMENT_CUSTOM_TERM_PREFIX + 'CONTENTTYPE'


class SearchBackend(BaseSearchBackend):
    def __init__(self, site=None, stem_lang='en'):
        super(SearchBackend, self).__init__(site)
        if not hasattr(settings, 'HAYSTACK_XAPIAN_PATH'):
            raise ImproperlyConfigured('You must specify a HAYSTACK_XAPIAN_PATH in your settings.')

        self.path = settings.HAYSTACK_XAPIAN_PATH
        self.stemmer = xapian.Stem('english')

        if not os.path.exists(self.path):
            os.makedirs(self.path)

    def update(self, index, iterable):
        database = xapian.WritableDatabase(self.path, xapian.DB_CREATE_OR_OPEN)
        indexer = xapian.TermGenerator()
        indexer.set_database(database)
        indexer.set_stemmer(self.stemmer)
        indexer.set_flags(xapian.TermGenerator.FLAG_SPELLING)

        fields_data = database.get_metadata('fields')
        if fields_data:
            fields = list(pickle.loads(fields_data))
        else:
            fields = []

        try:
            for obj in iterable:
                document_id = self.get_identifier(obj)
                document = xapian.Document()
                indexer.set_document(document)
                document.add_value(0, force_unicode(document_id))
                document_data = index.prepare(obj)

                for i, (key, value) in enumerate(document_data.iteritems()):
                    prefix = DOCUMENT_CUSTOM_TERM_PREFIX + self._from_python(key).upper()
                    data = self._from_python(value)
                    indexer.index_text(data)
                    indexer.index_text(data, 1, prefix)
                    fields.append(key)

                document.set_data(pickle.dumps(document_data, pickle.HIGHEST_PROTOCOL))
                document.add_term(DOCUMENT_ID_TERM_PREFIX + document_id)
                document.add_term(DOCUMENT_CT_TERM_PREFIX + u'%s.%s' % (obj._meta.app_label, obj._meta.module_name))

                database.replace_document(document_id, document)

            database.set_metadata('fields', pickle.dumps(set(fields)))

        except UnicodeDecodeError:
            sys.stderr.write('Chunk failed.\n')
            pass

    def remove(self, obj):
        database = xapian.WritableDatabase(self.path, xapian.DB_CREATE_OR_OPEN)
        database.delete_document(DOCUMENT_ID_TERM_PREFIX + self.get_identifier(obj))

    def clear(self, models=[]):
        database = xapian.WritableDatabase(self.path, xapian.DB_CREATE_OR_OPEN)
        if not models:
            query = xapian.Query('') # Empty query matches all
            enquire = xapian.Enquire(database)
            enquire.set_query(query)
            for match in enquire.get_mset(0, DEFAULT_MAX_RESULTS):
                database.delete_document(match.get_document().get_docid())
        else:
            for model in models:
                database.delete_document(DOCUMENT_CT_TERM_PREFIX + '%s.%s' % (model._meta.app_label, model._meta.module_name))

    def search(self, query_string, sort_by=None, start_offset=0, end_offset=DEFAULT_MAX_RESULTS,
               fields='', highlight=False, facets=None, date_facets=None, query_facets=None,
               narrow_queries=None, **kwargs):
        if not query_string:
            return {
                'results': [],
                'hits': 0,
            }

        if date_facets is not None:
            warnings.warn("Date faceting has not been implemented yet.", Warning, stacklevel=2)

        if query_facets is not None:
            warnings.warn("Query faceting has not been implemented yet.", Warning, stacklevel=2)

        if sort_by is not None:
            warnings.warn("Sorting has not been implemented yet.", Warning, stacklevel=2)

        if highlight is not None:
            warnings.warn("Highlight has not been implemented yet.", Warning, stacklevel=2)

        database = xapian.Database(self.path)
        if query_string == '*':
            query = xapian.Query('') # Make '*' match everything
        else:
            qp = xapian.QueryParser()
            qp.set_database(database)
            qp.set_stemmer(self.stemmer)
            qp.set_stemming_strategy(xapian.QueryParser.STEM_SOME)
            qp.add_boolean_prefix('django_ct', DOCUMENT_CT_TERM_PREFIX)
            for field in pickle.loads(database.get_metadata('fields')):
                qp.add_prefix(field, DOCUMENT_CUSTOM_TERM_PREFIX + field.upper())
            query = qp.parse_query(
                query_string, 
                xapian.QueryParser.FLAG_PARTIAL | xapian.QueryParser.FLAG_PHRASE |
                xapian.QueryParser.FLAG_BOOLEAN | xapian.QueryParser.FLAG_LOVEHATE |
                xapian.QueryParser.FLAG_WILDCARD
            )

        enquire = xapian.Enquire(database)
        enquire.set_query(query)
        matches = enquire.get_mset(start_offset, end_offset)

        return self._process_results(matches, facets)

    def delete_index(self):
        if os.path.exists(self.path):
            index_files = os.listdir(self.path)

            for index_file in index_files:
                os.remove(os.path.join(self.path, index_file))

            os.removedirs(self.path)

    def document_count(self):
        try:
            database = xapian.Database(self.path)
        except xapian.DatabaseOpeningError:
            return 0
        return database.get_doccount()

    def _process_results(self, matches, facets, highlights=[]):
        facets_dict = {
            'fields': {},
            'dates': {},
            'queries': {},
        }
        results = []
        hits = matches.get_matches_estimated()

        for match in matches:
            document = match.get_document()
            app_label, module_name, pk = document.get_value(0).split('.')
            additional_fields = pickle.loads(document.get_data())
            result = SearchResult(
                app_label, module_name, pk, match.weight, **additional_fields
            )
            results.append(result)

            if facets:
                facets_dict['fields'] = self._do_field_facets(document, facets, facets_dict['fields'])
                
        return {
            'results': results,
            'hits': hits,
            'facets': facets_dict,
        }

    def _do_field_facets(self, document, facets, fields):
        field_re = re.compile(r'(?<=(?<!Z)X)([A-Z_]+)(\w+)')
        term_list = [(term.term, term.termfreq) for term in document]
        for term in term_list:
            match = field_re.search(term[0])
            if match and match.group(1).lower() in facets:
                if match.group(1).lower() in fields:
                    fields[match.group(1).lower()] += [(match.group(2), term[1])]
                else:
                    fields[match.group(1).lower()] = [(match.group(2), term[1])]
        return fields

    def _from_python(self, value):
        """
        Converts Python values to a string for Xapian.
        Code courtesy of pysolr.
        """
        if isinstance(value, datetime.datetime):
            value = force_unicode('%s' % value.isoformat())
        elif isinstance(value, datetime.date):
            value = force_unicode('%sT00:00:00' % value.isoformat())
        elif isinstance(value, bool):
            if value:
                value = u'true'
            else:
                value = u'false'
        else:
            value = force_unicode(value)
        return value

    def more_like_this(self, model_instance):
        return {
            'results': [],
            'hits': 0,
        }


class SearchQuery(BaseSearchQuery):
    def __init__(self, backend=None):
        super(SearchQuery, self).__init__(backend=backend)
        self.backend = backend or SearchBackend()

    def build_query(self):
        query = ''

        if not self.query_filters:
            query = '*'
        else:
            query_chunks = []

            for the_filter in self.query_filters:
                if the_filter.is_and():
                    query_chunks.append('AND')
                
                if the_filter.is_not():
                    query_chunks.append('NOT')

                if the_filter.is_or():
                    query_chunks.append('OR')

                value = the_filter.value

                if not isinstance(value, (list, tuple)):
                    # Convert whatever we find to what xapian wants.
                    value = self.backend._from_python(value)

                # Check to see if it's a phrase for an exact match.
                if ' ' in value:
                    value = '"%s"' % value

                # 'content' is a special reserved word, much like 'pk' in
                # Django's ORM layer. It indicates 'no special field'.
                if the_filter.field == 'content':
                    query_chunks.append(value)
                else:
                    filter_types = {
                        'exact': "%s:%s",
                        'gt': "%s:%s..*",
                        'gte': "NOT %s:*..%s",
                        'lt': "%s:*..%s",
                        'lte': "NOT %s:%s..*",
                        'startswith': "%s:%s*",
                    }

                    if the_filter.filter_type != 'in':
                        query_chunks.append(filter_types[the_filter.filter_type] % (the_filter.field, value))
                    else:
                        in_options = []

                        for possible_value in value:
                            in_options.append("%s:%s" % (the_filter.field, possible_value))

                        query_chunks.append("(%s)" % " OR ".join(in_options))

            if query_chunks[0] in ('AND', 'OR'):
                # Pull off an undesirable leading "AND" or "OR".
                del(query_chunks[0])

            query = " ".join(query_chunks)

        if len(self.models):
            models = ['django_ct:%s.%s' % (model._meta.app_label, model._meta.module_name) for model in self.models]
            models_clause = ' '.join(models)
            final_query = '(%s) %s' % (query, models_clause)

        else:
            final_query = query

        # print final_query

        # TODO: Implement boost
        # if self.boost:
        #     boost_list = []
        # 
        #     for boost_word, boost_value in self.boost.items():
        #         boost_list.append("%s^%s" % (boost_word, boost_value))
        # 
        #     final_query = "%s %s" % (final_query, " ".join(boost_list))

        return final_query
    
    def clean(self, query_fragment):
        words = query_fragment.split()
        cleaned_words = []
        
        for word in words:
            if word in RESERVED_WORDS:
                word = word.replace(word, word.lower())
        
            for char in RESERVED_CHARACTERS:
                word = word.replace(char, '\\%s' % char)
            
            cleaned_words.append(word)
        
        return ' '.join(cleaned_words)
