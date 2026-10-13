# Reporting security issues

Do not post API keys, passwords, local network addresses, full printer configurations or private machine output in public issues. Use a sanitized minimal reproduction with project/version and the failing validation path.

For a flaw that could allow unexpected heater/motion commands or credential disclosure, contact the maintainer privately through the existing GitHub profile or supported private security reporting channel. Do not assume private reporting is enabled until GitHub displays it. Never ask another user to execute a reproducer on a printer before reviewing its movement and temperatures.

Builders do not upload, restart or print. Reviewed profiles and external toolchange macros remain trusted operator inputs. Report an accidental private-file inclusion promptly; do not solve it by force-pushing or deleting remote history without the owner's explicit authorization.
