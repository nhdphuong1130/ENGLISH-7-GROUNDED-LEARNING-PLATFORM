# System Password Autofill Design

## Goal

Make repeat sign-in convenient on Android and iOS/PWA by allowing the operating
system or browser password manager to suggest and fill previously saved account
credentials. The application must never persist plaintext passwords itself.

## User Experience

- Group the login identifier and password fields into one autofill context.
- Mark the identifier as a username and the secret as a password so Android,
  iOS, and supported browsers can present their native saved-account UI.
- After a complete successful login, ask the platform to save or update the
  credentials.
- Do not save credentials after an invalid login, a cancelled admin OTP flow,
  or a failed admin OTP verification.
- Logging out clears only the application session token. Saved credentials stay
  under the user's password-manager control.

## Architecture and Data Flow

The behavior remains entirely in the Flutter presentation layer. `LoginScreen`
owns the autofill context and tells Flutter to finish that context only after
authentication succeeds. A normal student login commits immediately after the
API returns a valid authenticated session. An admin login defers the commit
until the OTP challenge succeeds.

The existing `StudentApi` and backend contracts do not change. Passwords are
not written to SharedPreferences, application databases, logs, analytics, or
custom web storage. Android delegates storage to its configured credential
provider (commonly Google Password Manager); iOS and Safari delegate to Keychain
or the user's configured password manager.

## Failure Handling

Failed credentials leave the fields editable and cancel the current autofill
save request. Cancelling or failing the admin OTP dialog does the same. Existing
Vietnamese error messages remain visible and no credential details are included
in diagnostic output.

## Verification

Widget tests will verify the username/password autofill hints and the grouped
fields. Login-flow tests will verify that a successful student login commits the
autofill context, while admin authentication commits only after valid OTP.
Failure and cancellation paths must not request a save. Existing authentication,
session restoration, logout, Android, and PWA checks must continue to pass.
