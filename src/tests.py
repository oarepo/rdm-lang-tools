#
# Copyright (C) 2024 CESNET z.s.p.o.
#
# rdm-lang-tools is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.
#
import requests

url = (
    "https://rest.api.transifex.com/resource_translations?"
    "filter[resource]=o%3Ainveniosoftware%3Ap%3Ainvenio%3Ar%3Ainvenio-access-messages&"
    "filter[language]=l%3Ade"
)

headers = {
    "accept": "application/vnd.api+json",
    "authorization": "Bearer 1/2e6b07a78c3cb6d8b6644b702a0728e3c88382b6",
}

response = requests.get(url, headers=headers)

print(response.text)
