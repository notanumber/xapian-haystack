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

        self.stemming_language = stemming_language
        self.ready = False

    def _prepare(self, rw=False):
        """
        Prepare the required Xapian components for use.

        Optional arguments:
            `rw` -- Open the indexes in read/write mode (default=False)

        Verifies `HAYSTACK_XAPIAN_PATH` has been properly set and that the path
        specified is readable.  If it is not, tries to create the folder.
        """
        if self.ready:
            return

        if not os.path.exists(settings.HAYSTACK_XAPIAN_PATH):
            os.makedirs(settings.HAYSTACK_XAPIAN_PATH)

        if rw:
            self.database = xapian.WritableDatabase(settings.HAYSTACK_XAPIAN_PATH, xapian.DB_CREATE_OR_OPEN)
            self.content_field_name, fields = self.site.build_unified_schema()
            self.schema = self._build_schema(fields)
            self.database.set_metadata('schema', pickle.dumps(self.schema))
            self.database.set_metadata('cf', pickle.dumps(self.content_field_name))
            print self.schema
        else:
            self.database = xapian.Database(settings.HAYSTACK_XAPIAN_PATH)
            self.schema = pickle.loads(self.database.get_metadata('schema'))
            self.content_field_name = pickle.loads(self.database.get_metadata('cf'))

        self.stemmer = xapian.Stem(self.stemming_language)
        self.loaded = True

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
        self._prepare(rw=True)
        try:
            for obj in iterable:
                document_id = self.get_identifier(obj)
                document = xapian.Document()
                indexer = self._get_indexer(document)
                document.add_value(0, force_unicode(document_id))
                document_data = index.prepare(obj)

                for i, (key, value) in enumerate(document_data.iteritems()):
                    if key in self.schema:
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

                self.database.replace_document(DOCUMENT_ID_TERM_PREFIX + document_id, document)

        except UnicodeDecodeError:
            sys.stderr.write('Chunk failed.\n')
            pass

    def remove(self, obj):
        """
        Remove indexes for `obj` from the database.

        We delete all instances of `Q<app_name>.<model_name>.<pk>` which
        should be unique to this object.
        """
        self._prepare(rw=True)
        self.database.delete_document(DOCUMENT_ID_TERM_PREFIX + self.get_identifier(obj))

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
        self._prepare(rw=True)
        if not models:
            query = xapian.Query('') # Empty query matches all
            enquire = self._get_enquire(query)
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

        spelling_suggestion = None

        self._prepare()

        if query_string == '*':
            query = xapian.Query('') # Make '*' match everything
        else:
            flags = self._get_flags()
            qp = self._get_query_parser()
            query = qp.parse_query(query_string, flags)
            if getattr(settings, 'HAYSTACK_INCLUDE_SPELLING', False) is True:
                spelling_suggestion = qp.get_corrected_query_string()

        if narrow_queries:
            subqueries = [qp.parse_query(narrow_query, flags) for narrow_query in narrow_queries]
            query = xapian.Query(xapian.Query.OP_FILTER, query, xapian.Query(xapian.Query.OP_AND, subqueries))

        enquire = self._get_enquire(query)

        if sort_by:
            sorter = self._get_sorter(sort_by)
            enquire.set_sort_by_key_then_relevance(sorter, True)

        matches = enquire.get_mset(start_offset, end_offset)
        results = self._process_results(
            matches, query_string=query_string, highlight=highlight, facets=facets
        )

        if spelling_suggestion:
            results['spelling_suggestion'] = spelling_suggestion

        return results

    def delete_index(self):
        """
        Delete the index.
        
        This removes all indexes files and the `HAYSTACK_XAPIAN_PATH` folder.
        """
        if os.path.exists(settings.HAYSTACK_XAPIAN_PATH):
            index_files = os.listdir(settings.HAYSTACK_XAPIAN_PATH)

            for index_file in index_files:
                os.remove(os.path.join(settings.HAYSTACK_XAPIAN_PATH, index_file))

            os.removedirs(settings.HAYSTACK_XAPIAN_PATH)

    def document_count(self):
        """
        Retrieves the total document count for the search index.
        """
        try:
            if not self.loaded:
                self._load()
        except xapian.DatabaseOpeningError:
            return 0
        return self.database.get_doccount()

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
        if not self.loaded:
            self._load()

        query = xapian.Query(
            DOCUMENT_ID_TERM_PREFIX + self.get_identifier(model_instance)
        )
        enquire = self._get_enquire(query)
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

    def _process_results(self, matches, query_string='', highlight=False, facets=None):
        """
        Private method for processing an MSet (match set).

        Required arguments:
            `matches` -- An MSet of matches

        Optional arguments:
            `query_string` -- The query string that generated the matches
            `highlight` -- Add highlighting to results? (default=False)
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
            if highlight and (len(query_string) > 0):
                additional_fields['highlighted'] = {
                    self.content_field_name: self._do_highlight(
                        additional_fields.get(self.content_field_name), query_string
                    )
                }
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

    def _from_python(self, value):
        """
        Converts Python values to a string for Xapian.
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
        else:
            value = force_unicode(value)
        return value

    def _get_indexer(self, document):
        """
        Given a document, returns an Xapian.TermGenerator

        Required Argument:
            `document` -- The document to be indexed

        Returns a Xapian.TermGenerator instance
        """
        indexer = xapian.TermGenerator()
        indexer.set_database(self.database)
        indexer.set_stemmer(self.stemmer)
        indexer.set_flags(xapian.TermGenerator.FLAG_SPELLING)
        indexer.set_document(document)
        return indexer

    def _get_sorter(self, sort_by):
        """
        Given a list of fields to sort by, returns a xapian.MultiValueSorter

        Required Arguments:
            `sort_by` -- A list of fields to sort by

        Returns a xapian.MultiValueSorter instance
        """
        sorter = xapian.MultiValueSorter()
        for sort_field in sort_by:
            if sort_field.startswith('-'):
                reverse = False
                sort_field = sort_field[1:] # Strip the '-'
            else:
                reverse = True # Reverse is inverted in Xapian -- http://trac.xapian.org/ticket/311
            sorter.add(self.schema.get(sort_field, -1) + 1, reverse)
        return sorter

    def _get_flags(self):
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

    def _get_query_parser(self):
        """
        Returns a Xapian.QueryParser instance.

        The query parser returned will have stemming enabled, a boolean prefix
        for `django_ct`, and prefixes for all of the fields in the designated
        `schema`.
        """
        qp = xapian.QueryParser()
        qp.set_database(self.database)
        qp.set_stemmer(self.stemmer)
        qp.set_stemming_strategy(xapian.QueryParser.STEM_SOME)
        qp.add_boolean_prefix('django_ct', DOCUMENT_CT_TERM_PREFIX)
        for field in self.schema.keys():
            qp.add_prefix(field, DOCUMENT_CUSTOM_TERM_PREFIX + field.upper())
        return qp

    def _get_enquire(self, query):
        """
        Given a query, returns an Xapian.Enquire instance.

        Required Arguments:
            `query` -- The query to run

        Returns a xapian.Enquire instance
        """
        enquire = xapian.Enquire(self.database)
        enquire.set_query(query)
        enquire.set_docid_order(enquire.ASCENDING)
        return enquire

    def _build_schema(self, fields):
        """
        Private method to build a schema.

        Required arguments:
            ``fields`` -- A list of fields in the index

        Returns a list of fields in dictionary format ready for inclusion in
        an indexe meta-data.
        """
        for i, field in enumerate(fields):
            if field['indexed'] == 'true':
                field['column'] = i
            else:
                del field
        return fields


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