# eTranslation

reference: https://language-tools.ec.europa.eu/dev-corner/etranslation

## eTranslation scope

Toolkit implemented from UE for integrate multilingual support, accross all official languages of UE, into Digital Service.

We use the eTranslation APIs to translate the NDC portal bundles.

## eTranslation concept

- Domain Selection, choosing the translation domain that best fits your content

## eTranslation REST APIs v2

| API Specifications | Desccription | Reference |
|---|---|---|
| Authentication Method | Basic Authentication | https://language-tools.ec.europa.eu/dev-corner/authentication |
| Rate Limits | maximum number of active submissions <br> - 50 text snippets <br> - 50 documents <br> at a given time | https://language-tools.ec.europa.eu/dev-corner/etranslation/rest-v2/rate-limits |
| Message Exchange Pattern (MEP) | Asynchronous with Callback | https://language-tools.ec.europa.eu/dev-corner/efficient-consumption |
| Hard limit — text snippet | 5.000 characters | |
| Hard limit — document | 20 MB (base64 content) | |
| Target languages per request | Bundle all needed languages in one call | |
| API IDL | [openapi: 3.0.1](https://language-tools.ec.europa.eu/assets/downloads/eTranslation-RestV2.yaml) | https://language-tools.ec.europa.eu/dev-corner/etranslation/rest-v2/introduction |


## Glossary of terms not to be translated 

The “glossary” parameter of the /askTranslate endpoint allows you to specify a conditional glossary of terms.

One of the glossary formats is TSV, here is an example.

```csv
it  en  fr  de
turtle  turtle  turtle  turtle
RDF RDF RDF RDF
