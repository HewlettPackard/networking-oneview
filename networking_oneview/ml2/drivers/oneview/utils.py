import re


def id_from_uri(uri):
    if uri:
        return uri.split("/")[-1]


def uri_from_uuid(resource_prefix, uuid):
    if uuid:
        return str(resource_prefix) + str(uuid)
