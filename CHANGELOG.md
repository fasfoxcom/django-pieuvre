# Django-Pieuvre changelog

## Unreleased

...

## v0.6.2

- Make the permission name overridable so that inherited workflows can share the same permission

## v0.6.1

- Replace `applies_to` by a classmethod (instead of a static method) so that class name can be leveraged in the logic

## v0.6.0

- Workflows can define a staticmethod `applies_to` that takes an instance and returns whether or not the workflow applies to it.
- Model is changed to support MariaDB

## v0.5.1

- Prevent re-submitting Done tasks.

## Previous versions

...

## v0.3.1

- Changed default ordering for tasks: more recent first
