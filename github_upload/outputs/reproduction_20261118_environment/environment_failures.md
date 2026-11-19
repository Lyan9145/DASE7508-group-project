# Observed setup failures and remedies

- `conda env list`: CUDA virtual-package probing attempted a multiprocessing
  Windows pipe and raised PermissionError WinError 5; error reporting then raised
  KeyError user_agent. No report was sent. Used the registered mp1 executable
  directly (`C:/anaconda/envs/mp1/python.exe`).
- `mp1/python -m venv --system-site-packages .venv`: ensurepip subprocess exited
  1, leaving include-system-site-packages=false. Set the intended flag true in
  the local pyvenv.cfg; used existing uv to install locally. mp1 was not modified.
- pip initially unavailable in that partial venv. uv bypassed bootstrap pip;
  the inherited mp1 pip later worked with system site packages enabled.
- uv default cache: denied access to AppData/Local/uv/cache/sdists-v9/.git.
  Used UV_CACHE_DIR=$PWD/.uv-cache. Exact original outputs are in original_lock_uv.log.
- Restricted-network lock resolution: tunnel refused, Windows10061. Complete
  retry output is in original_lock_resolution.log. Approved network execution
  resolved the unchanged original lock (original_lock_network.log).
- First pytest invocation: 8 passed, 3 temporary-directory permission errors.
  Bare project collection also found two inaccessible pytest-cache temporary
  directories. Explicit test filenames and approved execution with a fresh
  project-local --basetemp passed all tests. Logs tests_original.log, tests.log,
  tests_verified.log, tests_final.log preserve attempts. These errors were not
  treated as product failures or silently removed.
- Get-CimInstance initially denied in sandbox. CPU identifier and core count
  were also saved via platform/environment; a read-only approved query then
  saved hardware.json.

No EGL variable was set. Numerics and RGB rendering passed independently.
Interactive human-window demo and screen recording still require a person at
the Windows desktop; no automatic claim of having watched that demo is made.

Final dependency audit found a declaration conflict: SB3 2.9.0 requires
Torch>=2.8, whereas inherited mp1 Torch was 2.7.1+cu126. See pip_check.log.
The first full numerical runs are retained as compatibility investigation.
Installed torch==2.14.1+cpu into .venv only using the original lock's CPU version;
pip_check_compatible.log now reports no broken requirements. All tests, numerical
checks, offscreen rendering, the complete main study and the development/test
exploration were repeated in that supported environment with new output paths.
