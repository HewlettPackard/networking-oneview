import re


def id_from_uri(uri):
    if uri:
        return uri.split("/")[-1]


def uri_from_id(resource_prefix, id):
    if id:
        return str(resource_prefix) + str(id)
