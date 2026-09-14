"""
Shared network setup for all request modules.

Why this exists:
On Android, ssl.create_default_context() (which httpx uses by default) tries
to read the OS certificate store. That path doesn't exist inside the
Flet/serious_python Android build, so every httpx.AsyncClient() call was
crashing with:

    FileNotFoundError: [Errno 2] No such file or directory
    File ".../ssl.py", line 717, in create_default_context

Fix: build the SSL context once from certifi's bundled cacert.pem (which
*is* packaged with the app) and pass it to every client via verify=.

Make sure `certifi` is listed as a dependency in pyproject.toml so its
cacert.pem actually ships in the Android build.
"""
import ssl
import certifi

ssl_context = ssl.create_default_context(cafile=certifi.where())