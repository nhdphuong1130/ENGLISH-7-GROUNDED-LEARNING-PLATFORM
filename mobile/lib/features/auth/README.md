# Auth feature

Authentication screens and state belong here. They communicate only through the
typed API client and token store.

Login credentials use Flutter's platform autofill context. Android and iOS/web
password managers own encrypted credential storage; the application never writes
passwords to its database or local preferences. The context is committed only
after normal authentication or the administrator OTP challenge succeeds.
