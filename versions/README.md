# Application versions

Lecturer-provided incremental versions of the ACEest application (Tkinter desktop
releases) that the Flask service in the repository root was ported from:

| File | Notes |
|---|---|
| Aceestver-1.0.py | Initial release |
| Aceestver-1.1.py, Aceestver1.1.2.py | 1.x feature/bug-fix releases |
| Aceestver2.0.1.py, Aceestver-2.1.2.py, Aceestver-2.2.1.py, Aceestver-2.2.4.py | 2.x releases |
| Aceestver-3.0.1.py, Aceestver-3.1.2.py, Aceestver-3.2.4.py | 3.x releases (business logic + SQLite schema reused in core.py / db.py) |

The deployable Flask application is versioned with Git tags (`v1.0.0`, `v2.0.0`, …) and the
matching Docker Hub image tags (`v1`, `v2`, `vN` from Jenkins builds, `latest`).
