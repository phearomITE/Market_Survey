CSV access fix

Dashboard and submissions CSV now return saved database records during the initial backfill, instead of HTTP 503. Data is partial until the first successful full sync; refresh after completion. Background sync continues automatically. Authentication and the public CSV opt-in remain unchanged. X-BI-Sync-State indicates initial-sync-in-progress until a full sync succeeds. An empty database returns headers only.
