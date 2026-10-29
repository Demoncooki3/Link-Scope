# Project workflow

The user explicitly requested that this project be kept updated on GitHub after every change.
Repository: https://github.com/Demoncooki3/Link-Scope (default branch: main).

- After each completed logical change, run the relevant checks, commit the project changes, and push them to the configured GitHub repository. This is standing authorization; do not repeatedly ask for permission to commit or push.
- Report a failed or blocked push accurately. Never claim GitHub is updated until the remote commit is verified.
- If local Git authentication is unavailable, use the connected GitHub tools to publish the changes and reconcile local history with the remote when possible.
- Do not force-push or overwrite unrelated remote work. Inspect remote changes first.
- Keep credentials, personal network reports, build caches, and generated binaries out of source control. Build distributables with build.ps1; GitHub Actions publishes portable builds as artifacts.
- Successful builds on main also publish the executable and ZIP as GitHub Release assets. Keep this distribution workflow working after changes.
- Preserve the documented diagnostic limits: link state is not continuity testing, logical topology is not a verified physical wiremap, and hostname lookup may fail.
- This workflow applies when working on the project. It is not a background filesystem watcher.
