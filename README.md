# Django-Pieuvre

Django-Pieuvre is a Django wrapper around Pieuvre, a simple yet powerful workflow engine library initially developed by [Kosc Telecom](https://www.kosc-telecom.fr/en/) and now maintained by [Fasfox](https://fasfox.com).
Django-Pieuvre is experimental. Its API should not be considered stable. It **will** break at some point.

## Getting Started

### Usage

This module provides superclasses above Pieuvre's Workflow and WorkflowEnabled classes, which allow persisted workflows.
Persisted workflows have an associated PieuvreProcess instance in database. When workflow transitions are set to be
manual (through the `manual=True` transition property), the workflow cannot advance automatically and a task is created instead.

Tasks are meant to be assigned to an user or to a group, so that only those users or groups can access them.

This module also provides viewsets based on Django-Rest-Framework to retrieve tasks.

Please check out the example (in the folder `example/`) for more insights. The test suite is partial but provides additional information.

### Prerequisites

- Python 3.6+
- Django 3.2+ (may work with previous versions)

### Installing

```
pip install django-pieuvre
```

## Authors

* **lerela** - [Fasfox](https://fasfox.com/)

## License

This project is licensed under the Apache License - see the [LICENSE.md](LICENSE.md) file for details

