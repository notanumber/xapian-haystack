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


DEFAULT_MAX_RESULTS = 100000

DOCUMENT_ID_TERM_PREFIX = 'Q'
DOCUMENT_CUSTOM_TERM_PREFIX = 'X'
DOCUMENT_CT_TERM_PREFIX = DOCUMENT_CUSTOM_TERM_PREFIX + 'CONTENTTYPE'


field_re = re.compile(r'(?<=(?<!Z)X)([A-Z_]+)(\w+)')


class SearchBackend(BaseSearchBackend):
    """
    `SearchBackend` defines the Xapian search backend for use with the Haystack
    API for Django search.

    It uses the Xapian Python bindings to interface with Xapian, and as
    such is subject to this bug: <http://trac.xapian.org/ticket/364> when
    Django is running with mod_python or mod_wsgi under Apache.

    Until this issue has been fixed by Xapian, it is neccessary to set
    `WSGIApplicationGroup to %{GLOBAL}` when using mod_wsgi, or
    `PythonInterpreter main_interpreter` when using mod_python.

    In order to use this backend, `HAYSTACK_XAPIAN_PATH` must be set in
    your settings.  This should point to a location where you would your
    indexes to reside.
    """
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

    def __init__(self, site=None, stem_lang='en'):
        """
        Instantiates an instance of `SearchBackend`.

        Optional arguments:
            `site` -- The site to associate the backend with (default = None)
            `stem_lang` -- The stemming language (default = 'en')

        Verifies `HAYSTACK_XAPIAN_PATH` has been properly set and that the path
        specified is readable.  If it is not, tries to create the folder.

        Also sets the stemming language to be used to `stem_lang`.
        """
        super(SearchBackend, self).__init__(site)
        if not hasattr(settings, 'HAYSTACK_XAPIAN_PATH'):
            raise ImproperlyConfigured('You must specify a HAYSTACK_XAPIAN_PATH in your settings.')

        self.path = settings.HAYSTACK_XAPIAN_PATH
        self.stemmer = xapian.Stem('english')

        if not os.path.exists(self.path):
            os.makedirs(self.path)

    def update(self, index, iterable):
        """
        Updates the `index` with any objects in `iterable` by adding/updating
        the database as needed.

        Required arguments:
            `index` -- The `SearchIndex` to process
            `iterable` -- An iterable of model instances to index

        For each object in `iterable`, a document is created containing all
        of the terms extracted from `index.prepare(obj)` with stemming prefixes,
        field prefixes, and 'as-is'.

        eg. `content:Testing` ==> `testing, Ztest, ZXCONTENTtest`

        Each document also contains two extra terms; a term in the format:
        
        `XCONTENTTYPE<app_name>.<model_name>`
        
        As well as a unique identifier in the the format:

        `Q<app_name>.<model_name>.<pk>`

        eg.: foo.bar (pk=1) ==> `Qfoo.bar.1`, `XCONTENTTYPEfoo.bar`
        
        This is useful for querying for a specific document corresponding to
        an model instance and is also stored in the document value field at
        position 0 for easy extraction.

        The document also contains a pickled version of the object itself in 
        the document data field.

        Also, the database itself maintains a list of all index field names
        in use through the database meta data field with the name `schema`.
        This is a pickled data that can be loaded on demand and used to assign 
        prefixes to query parsers so that a user can perform field name 
        filtering by simply querying as follow: 

        `<field_name>:<value>`

        eg.: `'foo:bar'` will filter based on the `foo` field for `bar`.
        
        Finally, we also store field values to be used for sorting data.  We
        store these in the document value slots (position zero is reserver
        for the document ID).  All values are stored as unicode strings with
        conversion of float, int, double, values being done by Xapian itself
        through the use of the :method:xapian.sortable_serialise method.
        """
        schema = self._build_schema()

        database = xapian.WritableDatabase(self.path, xapian.DB_CREATE_OR_OPEN)
        database.set_metadata('schema', pickle.dumps(schema))

        indexer = xapian.TermGenerator()
        indexer.set_database(database)
        indexer.set_stemmer(self.stemmer)
        indexer.set_flags(xapian.TermGenerator.FLAG_SPELLING)

        try:
            for obj in iterable:
                document_id = self.get_identifier(obj)
                document = xapian.Document()
                indexer.set_document(document)
                document.add_value(0, force_unicode(document_id))
                document_data = index.prepare(obj)

                for i, (key, value) in enumerate(document_data.iteritems()):
                    if key in schema:
                        prefix = DOCUMENT_CUSTOM_TERM_PREFIX + self._from_python(key).upper()
                        data = self._from_python(value)
                        indexer.index_text(data)
                        indexer.index_text(data, 1, prefix)

                        if isinstance(value, (int, long, float)):
                            document.add_value(i + 1, xapian.sortable_serialise(value))
                        else:
                            document.add_value(i + 1, data)

                document.set_data(pickle.dumps(document_data, pickle.HIGHEST_PROTOCOL))
                document.add_term(DOCUMENT_ID_TERM_PREFIX + document_id)
                document.add_term(
                    DOCUMENT_CT_TERM_PREFIX + u'%s.%s' % 
                    (obj._meta.app_label, obj._meta.module_name)
                )

                database.replace_document(DOCUMENT_ID_TERM_PREFIX + document_id, document)

        except UnicodeDecodeError:
            sys.stderr.write('Chunk failed.\n')
            pass

    def remove(self, obj):
        """
        Remove indexes for `obj` from the database.

        We delete all instances of `Q<app_name>.<model_name>.<pk>` which
        should be unique to this object.
        """
        database = xapian.WritableDatabase(self.path, xapian.DB_CREATE_OR_OPEN)
        database.delete_document(DOCUMENT_ID_TERM_PREFIX + self.get_identifier(obj))

    def clear(self, models=[]):
        """
        Clear all instances of `models` from the database or all models, if
        not specified.

        Optional Arguments:
            `models` -- Models to clear from the database (default = [])

        If `models` is empty, an empty query is executed which matches all
        documents in the database.  Afterwards, each match is deleted.
        
        Otherwise, for each model, a `delete_document` call is issued with
        the term `XCONTENTTYPE<app_name>.<model_name>`.  This will delete
        all documents with the specified model type.
        """
        database = xapian.WritableDatabase(self.path, xapian.DB_CREATE_OR_OPEN)
        if not models:
            query = xapian.Query('') # Empty query matches all
            enquire = xapian.Enquire(database)
            enquire.set_query(query)
            for match in enquire.get_mset(0, DEFAULT_MAX_RESULTS):
                database.delete_document(match.get_docid())
        else:
            for model in models:
                database.delete_document(
                    DOCUMENT_CT_TERM_PREFIX + '%s.%s' % 
                    (model._meta.app_label, model._meta.module_name)
                )

    def search(self, query_string, sort_by=None, start_offset=0, end_offset=DEFAULT_MAX_RESULTS,
               fields='', highlight=False, facets=None, date_facets=None, query_facets=None,
               narrow_queries=None, **kwargs):
        """
        Executes the search as defined in `query_string`.

        Required arguments:
            `query_string` -- Search query to execute

        Optional arguments:
            `sort_by` -- Sort results by specified field (default = None)
            `start_offset` -- Slice results from `start_offset` (default = 0)
            `end_offset` -- Slice results at `end_offset` (default = 10,000)
            `fields` -- Filter results on `fields` (default = '')
            `highlight` -- Highlight terms in results (default = False)
            `facets` -- Facet results on fields (default = None)
            `date_facets` -- Facet results on date ranges (default = None)
            `query_facets` -- Facet results on queries (default = None)
            `narrow_queries` -- Narrow queries (default = None)

        Returns:
            A dictionary with the following keys:
                `results` -- A list of `SearchResult`
                `hits` -- The total available results
                `facets` - A dictionary of facets with the following keys:
                    `fields` -- A list of field facets
                    `dates` -- A list of date facets
                    `queries` -- A list of query facets
            If faceting was not used, the `facets` key will not be present

        If `query_string` is empty, returns no results.
        
        Otherwise, loads the available fields from the database meta data schema
        and sets up prefixes for each one along with a prefix for `django_ct`,
        used to filter by model, and loads the current stemmer instance.

        Afterwards, executes the Xapian query parser to create a query from
        `query_string` that is then passed to a new `enquire` instance.
        
        The resulting match set is passed to :method:`_process_results` for
        further processing prior to returning a dictionary with the results.
        
        If `HAYSTACK_INCLUDE_SPELLING` was enabled in `settings.py`, the
        extra flag `FLAG_SPELLING_CORRECTION` will be passed to the query parser
        and any suggestions for spell correction will be returned as well as
        the results.
        """
        if not query_string:
            return {
                'results': [],
                'hits': 0,
            }

        if date_facets is not None:
            warnings.warn("Date faceting has not been implemented yet.", Warning, stacklevel=2)

        if query_facets is not None:
            warnings.warn("Query faceting has not been implemented yet.", Warning, stacklevel=2)

        if highlight is not False:
            warnings.warn("Highlight has not been implemented yet.", Warning, stacklevel=2)

        database = xapian.Database(self.path)
        schema = pickle.loads(database.get_metadata('schema'))
        spelling_suggestion = None

        if query_string == '*':
            query = xapian.Query('') # Make '*' match everything
        else:
            qp = xapian.QueryParser()
            qp.set_database(database)
            qp.set_stemmer(self.stemmer)
            qp.set_stemming_strategy(xapian.QueryParser.STEM_SOME)
            qp.add_boolean_prefix('django_ct', DOCUMENT_CT_TERM_PREFIX)
            for field in schema.keys():
                qp.add_prefix(field, DOCUMENT_CUSTOM_TERM_PREFIX + field.upper())
            flags = xapian.QueryParser.FLAG_PARTIAL \
                  | xapian.QueryParser.FLAG_PHRASE \
                  | xapian.QueryParser.FLAG_BOOLEAN \
                  | xapian.QueryParser.FLAG_LOVEHATE \
                  | xapian.QueryParser.FLAG_WILDCARD
            if getattr(settings, 'HAYSTACK_INCLUDE_SPELLING', False) is True:
                flags = flags | xapian.QueryParser.FLAG_SPELLING_CORRECTION
            query = qp.parse_query(query_string, flags)
            if getattr(settings, 'HAYSTACK_INCLUDE_SPELLING', False) is True:
                spelling_suggestion = qp.get_corrected_query_string()

        if narrow_queries:
            subqueries = [qp.parse_query(narrow_query, flags) for narrow_query in narrow_queries]
            query = xapian.Query(xapian.Query.OP_FILTER, query, xapian.Query(xapian.Query.OP_AND, subqueries))

        enquire = xapian.Enquire(database)
        enquire.set_query(query)
        enquire.set_docid_order(enquire.ASCENDING)

        if sort_by:
            sorter = xapian.MultiValueSorter()
            for sort_field in sort_by:
                if sort_field.startswith('-'):
                    reverse = False
                    sort_field = sort_field[1:] # Strip the '-'
                else:
                    reverse = True # Reverse is inverted in Xapian -- http://trac.xapian.org/ticket/311
                sorter.add(schema.get(sort_field, -1) + 1, reverse)
            enquire.set_sort_by_key_then_relevance(sorter, True)

        matches = enquire.get_mset(start_offset, end_offset)
        results = self._process_results(matches, facets)

        if spelling_suggestion:
            results['spelling_suggestion'] = spelling_suggestion

        return results

    def delete_index(self):
        """
        Delete the index.
        
        This removes all indexes files and the `HAYSTACK_XAPIAN_PATH` folder.
        """
        if os.path.exists(self.path):
            index_files = os.listdir(self.path)

            for index_file in index_files:
                os.remove(os.path.join(self.path, index_file))

            os.removedirs(self.path)

    def document_count(self):
        """
        Retrieves the total document count for the search index.
        """
        try:
            database = xapian.Database(self.path)
        except xapian.DatabaseOpeningError:
            return 0
        return database.get_doccount()

    def more_like_this(self, model_instance):
        """
        Given a model instance, returns a result set of similar documents.
        
        Required arguments:
            `model_instance` -- The model instance to use as a basis for
                                retrieving similar documents.

        Returns:
            A dictionary with the following keys:
                `results` -- A list of `SearchResult`
                `hits` -- The total available results

        Opens a database connection, then builds a simple query using the
        `model_instance` to build the unique identifier.

        For each document retrieved(should always be one), adds an entry into
        an RSet (relevance set) with the document id, then, uses the RSet
        to query for an ESet (A set of terms that can be used to suggest
        expansions to the original query), omitting any document that was in
        the original query.

        Finally, processes the resulting matches and returns.
        """
        database = xapian.Database(self.path)
        query = xapian.Query(
            DOCUMENT_ID_TERM_PREFIX + self.get_identifier(model_instance)
        )
        enquire = xapian.Enquire(database)
        enquire.set_query(query)
        enquire.set_docid_order(enquire.DONT_CARE)
        rset = xapian.RSet()
        for match in enquire.get_mset(0, DEFAULT_MAX_RESULTS):
            rset.add_document(match.get_docid())
        query = xapian.Query(xapian.Query.OP_OR,
            [expand.term for expand in enquire.get_eset(DEFAULT_MAX_RESULTS, rset)]
        )
        query = xapian.Query(xapian.Query.OP_AND_NOT,
            [query, DOCUMENT_ID_TERM_PREFIX + self.get_identifier(model_instance)]
        )
        enquire.set_query(query)
        matches = enquire.get_mset(0, DEFAULT_MAX_RESULTS)
        return self._process_results(matches)

    def _process_results(self, matches, facets=None):
        """
        Private method for processing an MSet (match set).

        Required arguments:
            `matches` -- An MSet of matches

        Optional arguments:
            `facets` -- Fields to facet (default = None)

        Returns:
            A dictionary with the following keys:
                `results` -- A list of `SearchResult`
                `hits` -- The total available results
                `facets` - A dictionary of facets with the following keys:
                    `fields` -- A list of field facets
                    `dates` -- A list of date facets
                    `queries` -- A list of query facets
            If faceting was not used, the `facets` key will not be present
        
        For each match in the `matches`, retrieves the corresponding document
        and extracts the `app_name`, `model_name`, and `pk` from the information
        at value position 0, and :method:pickle.loads the remaining model
        values from the document data area.
        
        For each match, one `SearchResult` will be appended to the `results`
        list.
        """
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
                facets_dict['fields'] = self._do_field_facets(
                    document, facets, facets_dict['fields']
                )

        return {
            'results': results,
            'hits': hits,
            'facets': facets_dict,
        }

    def _do_field_facets(self, document, facets, fields):
        """
        Private method that facets a document by field name.

        Required arguments:
            `document` -- The document to parse
            `facets` -- A list of facets to use when faceting
            `fields` -- A list of fields that have already been faceted. This
                        will be extended with any new field names and counts
                        found in the `document`.

        For each term in the document, extract the field name and determine
        if it is one of the `facets` we want.  If so, verify if it already in
        the `fields` list.  If it is, update the count, otherwise, add it and
        set the count to 1.
        """
        for term in [(term.term, term.termfreq) for term in document]:
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

        Original code courtesy of pysolr.
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

    def _build_schema(self):
        """
        Builds a Xapian backend specific schema

        Returns a dictionary that can be stored in the database ('schema') metdata.
        """
        content_field_name, fields = self.site.build_unified_schema()
        schema_fields = {}
        for i, field in enumerate(fields):
            if field['indexed'] == 'true':
                schema_fields[field['field_name']] = i
        return schema_fields


class SearchQuery(BaseSearchQuery):
    """
    `SearchQuery` is responsible for converting search queries into a format
    that Xapian can understand.

    Most of the work is done by the :method:`build_query`.
    """
    def __init__(self, backend=None):
        """
        Create a new instance of the SearchQuery setting the backend as
        specified.  If no backend is set, will use the Xapian `SearchBackend`.

        Optional arguments:
            `backend` -- The `SearchBackend` to use (default = None)
        """
        super(SearchQuery, self).__init__(backend=backend)
        self.backend = backend or SearchBackend()

    def build_query(self):
        """
        Builds a search query from previously set values, returning a query
        string in a format ready for use by the Xapian `SearchBackend`.

        Returns:
            A query string suitable for parsing by Xapian.
        """
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