# Opportunity Lifecycle V1 implementation notes

- Reuses the existing canonical enums in `unified_models.py`.
- Adds one pure classifier in `opportunity_lifecycle.py`.
- Routes `opportunity_record_from_discovery_candidate` through the classifier.
- Stores a stable `lifecycle_reason_code` in record metadata for later transition history.
- Keeps persistence and daily checkpoint integration out of this pull request.
