# Copyright 2017 The Armada Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import collections
import json
import yaml

from armada.exceptions import override_exceptions
from armada.exceptions import validate_exceptions
from armada.handlers import schema
from armada.utils import validate


class Override(object):

    def __init__(self, documents, overrides=None, values=None):
        self.documents = documents
        self.overrides = overrides
        self.values = values

    def _load_yaml_file(self, doc):
        '''
        Retrieve yaml file as a dictionary.
        '''
        try:
            with open(doc) as f:
                return list(yaml.safe_load_all(f.read()))
        except IOError:
            raise override_exceptions.InvalidOverrideFileException(doc)

    def _document_checker(self, doc, ovr=None):
        # Validate document or raise the appropriate exception
        try:
            valid, details = validate.validate_armada_documents(doc)
        except (RuntimeError, TypeError):
            raise override_exceptions.InvalidOverrideValueException(ovr)
        if not valid:
            if ovr:
                raise override_exceptions.InvalidOverrideValueException(ovr)
            else:
                raise validate_exceptions.InvalidManifestException(
                    error_messages=details)

    def update(self, d, u):
        for k, v in u.items():
            if isinstance(v, collections.Mapping):
                r = self.update(d.get(k, {}), v)
                d[k] = r
            elif isinstance(v, str) and isinstance(d.get(k), (list, tuple)):
                d[k] = [x.strip() for x in v.split(',')]
            else:
                d[k] = u[k]
        return d

    def find_document_type(self, alias):
        if alias == 'chart_group':
            return schema.TYPE_CHARTGROUP
        if alias == 'chart':
            return schema.TYPE_CHART
        if alias == 'manifest':
            return schema.TYPE_MANIFEST
        else:
            raise ValueError("Could not find {} document".format(alias))

    def find_manifest_document(self, doc_path):
        for doc in self.documents:
            schema_info = schema.get_schema_info(doc.get('schema'))
            if schema_info.type == self.find_document_type(
                    doc_path[0]) and doc.get('metadata',
                                             {}).get('name') == doc_path[1]:
                return doc

        raise override_exceptions.UnknownDocumentOverrideException(
            doc_path[0], doc_path[1])

    def array_to_dict(self, data_path, new_value):
        # TODO(fmontei): Handle `json.decoder.JSONDecodeError` getting thrown
        # better.
        def convert(data):
            if isinstance(data, str):
                return str(data)
            elif isinstance(data, collections.Mapping):
                return dict(map(convert, data.items()))
            elif isinstance(data, collections.Iterable):
                return type(data)(map(convert, data))
            else:
                return data

        if not new_value:
            return

        if not data_path:
            return

        tree = {}

        t = tree
        for part in data_path:
            if part == data_path[-1]:
                t.setdefault(part, None)
                continue
            t = t.setdefault(part, {})

        string = json.dumps(tree).replace('null', '"{}"'.format(new_value))
        data_obj = convert(json.loads(string, encoding='utf-8'))

        return data_obj

    def override_manifest_value(self, doc_path, data_path, new_value):
        document = self.find_manifest_document(doc_path)
        new_data = self.array_to_dict(data_path, new_value)
        self.update(document.get('data', {}), new_data)

    def update_documents(self, merging_values):
        for doc in merging_values:
            self.update_document(doc)

    def update_document(self, ovr):
        ovr_schema_info = schema.get_schema_info(ovr.get('schema'))
        if ovr_schema_info:
            for doc in self.documents:
                schema_info = schema.get_schema_info(doc.get('schema'))
                if schema_info:
                    if schema_info == ovr_schema_info:
                        if doc['metadata']['name'] == ovr['metadata']['name']:
                            data = doc.get('data', {})
                            ovr_data = ovr.get('data', {})
                            self.update(data, ovr_data)
                            return

    def update_manifests(self):

        if self.values:
            for value in self.values:
                merging_values = self._load_yaml_file(value)
                self.update_documents(merging_values)
            # Validate document with updated values
            self._document_checker(self.documents, self.values)

        if self.overrides:
            for override in self.overrides:
                new_value = override.split('=', 1)[1]
                doc_path = override.split('=', 1)[0].split(":")
                data_path = doc_path.pop().split('.')

                self.override_manifest_value(doc_path, data_path, new_value)
            # Validate document with overrides
            self._document_checker(self.documents, self.overrides)

        if not (self.values and self.overrides):
            # Valiate document
            self._document_checker(self.documents)

        return self.documents
