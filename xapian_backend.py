# Copyright (C) 2009 David Sauve
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import datetime
import cPickle as pickle
import os
import re
import shutil
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


class XHValueRangeProcessor(xapian.ValueRangeProcessor):
    def __init__(self, sb):
        self.sb = sb
        xapian.ValueRangeProcessor.__init__(self)

    def __call__(self, begin, end):
        """
        Construct a tuple for value range processing.
        
        `begin` -- a string in the format '<field_name>:[low_range]'
                   If 'low_range' is omitted, assume the smallest possible value.
        `end` -- a string in the the format '[high_range|*]'.  If '*', assume
                 the highest possible value.
        
        Return a tuple of three strings: (column, low, high)
        """
        colon = begin.find(':')
        field_name = begin[:colon]
        begin = begin[colon + 1:len(begin)]
        for field_dict in self.sb.schema:
            if field_dict['field_name'] == field_name:
                if not begin:
                    if field_dict['type'] == 'text':
                        begin = u'a' # TODO: A better way of getting a min text value?
                    elif field_dict['type'] == 'long' or field_dict['type'] == 'float':
                        begin = float('-inf')
                    elif field_dict['type'] == 'date' or field_dict['type'] == 'datetime':
                        begin = u'00010101000000'
                elif end == '*':
                    if field_dict['type'] == 'text':
                        end = u'z' * 100 # TODO: A better way of getting a max text value?
                    elif field_dict['type'] == 'long' or field_dict['type'] == 'float':
                        end = float('inf')
                    elif field_dict['type'] == 'date' or field_dict['type'] == 'datetime':
                        end = u'99990101000000'
                if field_dict['type'] == 'long' or field_dict['type'] == 'float':
                    begin = xapian.sortable_serialise(float(begin))
                    end = xapian.sortable_serialise(float(end))
                return field_dict['column'], str(begin), str(end)


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

    def __init__(self, site=None, stemming_language='english'):
        """
        Instantiates an instance of `SearchBackend`.

        Optional arguments:
            `site` -- The site to associate the backend with (default = None)
            `stemming_language` -- The stemming language (default = 'english')

        Also sets the stemming language to be used to `stemming_language`.
        """
        super(SearchBackend, self).__init__(site)

        if not hasattr(settings, 'HAYSTACK_XAPIAN_PATH'):
            raise ImproperlyConfigured('You must specify a HAYSTACK_XAPIAN_PATH in your settings.')

        if not os.path.exists(settings.HAYSTACK_XAPIAN_PATH):
            os.makedirs(settings.HAYSTACK_XAPIAN_PATH)

        self.stemmer = xapian.Stem(stemming_language)

    def get_identifier(self, obj_or_string):
        return DOCUMENT_ID_TERM_PREFIX + super(SearchBackend, self).get_identifier(obj_or_string)

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

        Each document also contains an extra term in the format:
        
        `XCONTENTTYPE<app_name>.<model_name>`
        
        As well as a unique identifier in the the format:

        `Q<app_name>.<model_name>.<pk>`

        eg.: foo.bar (pk=1) ==> `Qfoo.bar.1`, `XCONTENTTYPEfoo.bar`
        
        This is useful for querying for a specific document corresponding to
        a model instance.

        The document also contains a pickled version of the object itself and
        the document ID in the document data field.

        Finally, we also store field values to be used for sorting data.  We
        store these in the document value slots (position zero is reserver
        for the document ID).  All values are stored as unicode strings with
        conversion of float, int, double, values being done by Xapian itself
        through the use of the :method:xapian.sortable_serialise method.
        """
        database = self._database(writable=True)
        try:
            for obj in iterable:
                document = xapian.Document()
                term_generator = self._term_generator(database, document)
                document_id = self.get_identifier(obj)
                model_data = index.prepare(obj)

                for field in self.schema:
                    if field['field_name'] in model_data.keys():
                        prefix = DOCUMENT_CUSTOM_TERM_PREFIX + field['field_name'].upper()
                        value = model_data[field['field_name']]
                        term_generator.index_text(force_unicode(value))
                        term_generator.index_text(force_unicode(value), 1, prefix)
                        document.add_value(field['column'], self._marshal_value(value))

                document.set_data(pickle.dumps(
                    (obj._meta.app_label, obj._meta.module_name, obj.pk, model_data), 
                    pickle.HIGHEST_PROTOCOL
                ))
                document.add_term(document_id)
                document.add_term(
                    DOCUMENT_CT_TERM_PREFIX + u'%s.%s' % 
                    (obj._meta.app_label, obj._meta.module_name)
                )
                database.replace_document(document_id, document)

        except UnicodeDecodeError:
            sys.stderr.write('Chunk failed.\n')
            pass

    def remove(self, obj):
        """
        Remove indexes for `obj` from the database.

        We delete all instances of `Q<app_name>.<model_name>.<pk>` which
        should be unique to this object.
        """
        database = self._database(writable=True)
        database.delete_document(self.get_identifier(obj))

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
        database = self._database(writable=True)
        if not models:
            query, __unused__ = self._query(database, '*')
            enquire = self._enquire(database, query)
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

        database = self._database()
        query, spelling_suggestion = self._query(database, query_string, narrow_queries)
        enquire = self._enquire(database, query)

        if sort_by:
            sorter = self._sorter(sort_by)
            enquire.set_sort_by_key_then_relevance(sorter, True)

        results = []
        facets_dict = {
            'fields': {},
            'dates': {},
            'queries': {},
        }
        matches = enquire.get_mset(start_offset, end_offset)

        for match in matches:
            document = match.get_document()
            app_label, module_name, pk, model_data = pickle.loads(document.get_data())
            if facets:
                facets_dict['fields'] = self._do_field_facets(
                    document, facets, facets_dict['fields']
                )
            if highlight and (len(query_string) > 0):
                model_data['highlighted'] = {
                    self.content_field_name: self._do_highlight(
                        model_data.get(self.content_field_name), query_string
                    )
                }
            results.append(
                SearchResult(app_label, module_name, pk, match.weight, **model_data)
            )

        return {
            'results': results,
            'hits': matches.get_matches_estimated(),
            'facets': facets_dict,
            'spelling_suggestion': spelling_suggestion,
        }

    def delete_index(self):
        """
        Delete the index.
        
        This removes all indexes files and the `HAYSTACK_XAPIAN_PATH` folder.
        """
        if os.path.exists(settings.HAYSTACK_XAPIAN_PATH):
            shutil.rmtree(settings.HAYSTACK_XAPIAN_PATH)

    def document_count(self):
        """
        Retrieves the total document count for the search index.
        """
        try:
            database = self._database()
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
        database = self._database()
        query = xapian.Query(self.get_identifier(model_instance))
        enquire = self._enquire(database, query)
        rset = xapian.RSet()
        for match in enquire.get_mset(0, DEFAULT_MAX_RESULTS):
            rset.add_document(match.get_docid())
        query = xapian.Query(xapian.Query.OP_OR,
            [expand.term for expand in enquire.get_eset(DEFAULT_MAX_RESULTS, rset)]
        )
        query = xapian.Query(
            xapian.Query.OP_AND_NOT, [query, self.get_identifier(model_instance)]
        )
        enquire.set_query(query)

        results = []
        matches = enquire.get_mset(0, DEFAULT_MAX_RESULTS)
        
        for match in matches:
            document = match.get_document()
            app_label, module_name, pk, model_data = pickle.loads(document.get_data())
            results.append(
                SearchResult(app_label, module_name, pk, match.weight, **model_data)
            )

        return {
            'results': results,
            'hits': matches.get_matches_estimated(),
            'facets': {
                'fields': {},
                'dates': {},
                'queries': {},
            },
            'spelling_suggestion': None,
        }

    def _do_highlight(self, content, text, tag='em'):
        """
        Highlight `text` in `content` with html `tag`.
        
        This method assumes that the input text (`content`) does not contain
        any special formatting.  That is, it does not contain any html tags
        or similar markup that could be screwed up by the highlighting.
        
        Required arguments:
            `content` -- Content to search for instances of `text`
            `text` -- The text to be highlighted
        """
        for term in [term.replace('*', '') for term in text.split()]:
            term_re = re.compile(re.escape(term), re.IGNORECASE)
            content = term_re.sub('<%s>%s</%s>' % (tag, term, tag), content)
        return content

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

    def _marshal_value(self, value):
        """
        Private method that converts Python values to a string for Xapian values.
        """
        if isinstance(value, datetime.datetime):
            if value.microsecond:
                value = u'%04d%02d%02d%02d%02d%02d%06d' % (
                    value.year, value.month, value.day, value.hour, 
                    value.minute, value.second, value.microsecond
                )
            else:
                value = u'%04d%02d%02d%02d%02d%02d' % (
                    value.year, value.month, value.day, value.hour, 
                    value.minute, value.second
                )
        elif isinstance(value, datetime.date):
            value = u'%04d%02d%02d000000' % (value.year, value.month, value.day)
        elif isinstance(value, bool):
            if value:
                value = u't'
            else:
                value = u'f'
        elif isinstance(value, (int, long, float)):
            value = xapian.sortable_serialise(value)
        else:
            value = force_unicode(value)
        return value

    def _database(self, writable=False):
        """
        Private method that returns a xapian.Database for use and sets up
        schema and content_field definitions.

        Optional arguments:
            ``writable`` -- Open the database in read/write mode (default=False)

        Returns an instance of a xapian.Database or xapian.WritableDatabase
        """
        if writable:
            self.content_field_name, fields = self.site.build_unified_schema()
            self.schema = self._build_schema(fields)

            database = xapian.WritableDatabase(settings.HAYSTACK_XAPIAN_PATH, xapian.DB_CREATE_OR_OPEN)
            database.set_metadata('schema', pickle.dumps(self.schema, pickle.HIGHEST_PROTOCOL))
            database.set_metadata('content', pickle.dumps(self.content_field_name, pickle.HIGHEST_PROTOCOL))
        else:
            database = xapian.Database(settings.HAYSTACK_XAPIAN_PATH)

            self.schema = pickle.loads(database.get_metadata('schema'))
            self.content_field_name = pickle.loads(database.get_metadata('content'))

        return database

    def _term_generator(self, database, document):
        """
        Private method that returns a Xapian.TermGenerator

        Required Argument:
            `document` -- The document to be indexed

        Returns a Xapian.TermGenerator instance.  If `HAYSTACK_INCLUDE_SPELLING`
        is True, then the term generator will have spell-checking enabled.
        """
        term_generator = xapian.TermGenerator()
        term_generator.set_database(database)
        term_generator.set_stemmer(self.stemmer)
        if getattr(settings, 'HAYSTACK_INCLUDE_SPELLING', False) is True:
            term_generator.set_flags(xapian.TermGenerator.FLAG_SPELLING)
        term_generator.set_document(document)
        return term_generator

    def _query(self, database, query_string, narrow_queries=None):
        """
        Private method that takes a query string and returns a xapian.Query.
        
        Required arguments:
            `query_string` -- The query string to parse
        
        Optional arguments:
            `narrow_queries` -- A list of queries to narrow the query with
        
        Returns a xapian.Query instance with prefixes and ranges properly
        setup as pulled from the `query_string`.
        """
        spelling_suggestion = None

        if query_string == '*':
            query = xapian.Query('') # Make '*' match everything
        else:
            flags = self._flags()
            qp = self._query_parser(database)
            vrp = XHValueRangeProcessor(self)
            qp.add_valuerangeprocessor(vrp)
            query = qp.parse_query(query_string, flags)
            if getattr(settings, 'HAYSTACK_INCLUDE_SPELLING', False) is True:
                spelling_suggestion = qp.get_corrected_query_string()
    
        if narrow_queries:
            subqueries = [
                qp.parse_query(narrow_query, flags) for narrow_query in narrow_queries
            ]
            query = xapian.Query(
                xapian.Query.OP_FILTER, 
                query, xapian.Query(xapian.Query.OP_AND, subqueries)
            )
            
        return query, spelling_suggestion

    def _sorter(self, sort_by):
        """
        Private methos that takes a list of fields to sort by and returns a 
        xapian.MultiValueSorter

        Required Arguments:
            `sort_by` -- A list of fields to sort by

        Returns a xapian.MultiValueSorter instance
        """
        sorter = xapian.MultiValueSorter()
        
        for sort_field in sort_by:
            if sort_field.startswith('-'):
                reverse = True
                sort_field = sort_field[1:] # Strip the '-'
            else:
                reverse = False # Reverse is inverted in Xapian -- http://trac.xapian.org/ticket/311
            sorter.add(self._value_column(sort_field), reverse)
            
        return sorter

    def _flags(self):
        """
        Returns the commonly used Xapian.QueryParser flags
        """
        flags = xapian.QueryParser.FLAG_PARTIAL \
              | xapian.QueryParser.FLAG_PHRASE \
              | xapian.QueryParser.FLAG_BOOLEAN \
              | xapian.QueryParser.FLAG_LOVEHATE \
              | xapian.QueryParser.FLAG_WILDCARD \
              | xapian.QueryParser.FLAG_PURE_NOT
        if getattr(settings, 'HAYSTACK_INCLUDE_SPELLING', False) is True:
            flags = flags | xapian.QueryParser.FLAG_SPELLING_CORRECTION
        return flags

    def _query_parser(self, database):
        """
        Private method that returns a Xapian.QueryParser instance.

        Required arguments:
            `database` -- The database to be queried

        The query parser returned will have stemming enabled, a boolean prefix
        for `django_ct`, and prefixes for all of the fields in the `self.schema`.
        """
        qp = xapian.QueryParser()
        qp.set_database(database)
        qp.set_stemmer(self.stemmer)
        qp.set_stemming_strategy(xapian.QueryParser.STEM_SOME)
        qp.add_boolean_prefix('django_ct', DOCUMENT_CT_TERM_PREFIX)
        for field_dict in self.schema:
            qp.add_prefix(
                field_dict['field_name'], 
                DOCUMENT_CUSTOM_TERM_PREFIX + field_dict['field_name'].upper()
            )
        return qp

    def _enquire(self, database, query):
        """
        Private method that that returns a Xapian.Enquire instance for use with
        the specifed `query`.

        Required Arguments:
            `query` -- The query to run

        Returns a xapian.Enquire instance
        """
        enquire = xapian.Enquire(database)
        enquire.set_query(query)
        enquire.set_docid_order(enquire.ASCENDING)
        
        return enquire

    def _build_schema(self, fields):
        """
        Private method to build a schema.

        Required arguments:
            ``fields`` -- A list of fields in the index

        Returns a list of fields in dictionary format ready for inclusion in
        an indexed meta-data.
        """
        schema = []
        n = 0
        for field in fields:
            if field['indexed'] == 'true':
                field['column'] = n
                n += 1
                schema.append(field)
        return schema

    def _value_column(self, field):
        """
        Private method that returns the column value slot in the database
        for a given field.

        Required arguemnts:
            `field` -- The field to lookup

        Returns an integer with the column location (0 indexed).
        """
        for field_dict in self.schema:
            if field_dict['field_name'] == field:
                return field_dict['column']
        return 0


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
                    value = self.backend._marshal_value(value)

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
                        'gte': "%s:%s..*",
                        'gt': "NOT %s:..%s",
                        'lte': "%s:..%s",
                        'lt': "NOT %s:%s..*",
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