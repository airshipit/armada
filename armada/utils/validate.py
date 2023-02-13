# Copyright 2017 AT&T Intellectual Property.  All other rights reserved.
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

import traceback

import jsonschema
import requests
from oslo_log import log as logging

from armada import const
from armada.handlers import schema as sch
from armada.handlers.manifest import Manifest
from armada.exceptions.manifest_exceptions import ManifestException
from armada.utils.validation_message import ValidationMessage

LOG = logging.getLogger(__name__)


def _validate_armada_manifest(manifest):
    """Validates an Armada manifest file output by
    :class:`armada.handlers.manifest.Manifest`.

    This will do business logic validation after the input
    files have be syntactically validated via jsonschema.

    :param dict manifest: The manifest to validate.

    :returns: A tuple of (bool, list[dict]) where the first value
        indicates whether the validation succeeded or failed and
        the second value is the validation details with a minimum
        keyset of (message(str), error(bool))
    :rtype: tuple.
    """
    details = []

    try:
        manifest.get_manifest().get(const.KEYWORD_DATA)
    except ManifestException as me:
        vmsg = ValidationMessage(
            message=str(me), error=True, name='ARM001', level='Error')
        LOG.error(traceback.format_exc())
        LOG.error('ValidationMessage: %s', vmsg.get_output_json())
        details.append(vmsg.get_output())
        return False, details

    if len([x for x in details if x.get('error', False)]) > 0:
        return False, details

    return True, details


def validate_armada_manifests(documents):
    """Validate each Armada manifest found in the document set.

    :param documents: List of Armada documents to validate
    :type documents: :func: `list[dict]`.
    """
    messages = []
    all_valid = True

    for document in documents:
        doc_schema = document.get('schema')
        if doc_schema:
            schema_info = sch.get_schema_info(doc_schema)
            if schema_info and schema_info.type == sch.TYPE_MANIFEST:
                target = document.get('metadata').get('name')
                # TODO(MarshM) explore: why does this pass 'documents'?
                manifest = Manifest(documents, target_manifest=target)
                is_valid, details = _validate_armada_manifest(manifest)
                all_valid = all_valid and is_valid
                messages.extend(details)

    return all_valid, messages


def validate_armada_document(document):
    """Validates a document ingested by Armada by subjecting it to JSON schema
    validation.

    :param dict dictionary: The document to validate.

    :returns: A tuple of (bool, list[dict]) where the first value
        indicates whether the validation succeeded or failed and
        the second value is the validation details with a minimum
        keyset of (message(str), error(bool))
    :rtype: tuple.
    :raises TypeError: If ``document`` is not of type ``dict``.

    """
    if not isinstance(document, dict):
        raise TypeError(
            'The provided input "%s" must be a dictionary.' % document)

    schema = document.get('schema', '<missing>')
    document_name = document.get('metadata', {}).get('name', None)
    details = []
    LOG.debug('Validating document [%s] %s', schema, document_name)

    schema_info = sch.get_schema_info(schema)
    if schema_info:
        try:
            validator = jsonschema.Draft4Validator(schema_info.data)
            for error in validator.iter_errors(document.get('data')):
                error_message = "Invalid document [%s] %s: %s." % \
                    (schema, document_name, error.message)
                vmsg = ValidationMessage(
                    message=error_message,
                    error=True,
                    name='ARM100',
                    level='Error',
                    schema=schema,
                    doc_name=document_name)
                LOG.info('ValidationMessage: %s', vmsg.get_output_json())
                details.append(vmsg.get_output())
        except jsonschema.SchemaError as e:
            error_message = (
                'The built-in Armada JSON schema %s is invalid. '
                'Details: %s.' % (e.schema, e.message))
            vmsg = ValidationMessage(
                message=error_message,
                error=True,
                name='ARM000',
                level='Error',
                diagnostic='Armada is misconfigured.')
            LOG.error('ValidationMessage: %s', vmsg.get_output_json())
            details.append(vmsg.get_output())

    if len([x for x in details if x.get('error', False)]) > 0:
        return False, details

    return True, details


def validate_armada_documents(documents):
    """Validates multiple Armada documents.

    :param documents: List of Armada manifests to validate.
    :type documents: :func:`list[dict]`.

    :returns: A tuple of bool, list[dict] where the first value is whether
        the full set of documents is valid or not and the second is the
        detail messages from validation
    :rtype: tuple
    """
    messages = []
    # Track if all the documents in the set are valid
    all_valid = True

    for document in documents:
        is_valid, details = validate_armada_document(document)
        all_valid = all_valid and is_valid
        messages.extend(details)

    if all_valid:
        valid, details = validate_armada_manifests(documents)
        all_valid = all_valid and valid
        messages.extend(details)
        for msg in messages:
            if msg.get('error', False):
                LOG.error(msg.get('message', 'Unknown validation error.'))
            else:
                LOG.debug(msg.get('message', 'Validation succeeded.'))

    return all_valid, messages


def validate_manifest_url(value):
    try:
        return (requests.get(value, timeout=5).status_code == 200)
    except requests.exceptions.RequestException:
        return False
