# Executed from repository root / github_upload as indicated. mp1 is the base.
# Outputs in this record already exist: use a fresh suffix for a new run.
# Root:
& C:/anaconda/envs/mp1/python.exe -m venv --system-site-packages .venv
# ensurepip failed; enable system-site-packages in pyvenv.cfg, then use uv.
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
uv pip install --python .venv/Scripts/python.exe --dry-run -r github_upload/requirements.lock.txt
uv pip install --python .venv/Scripts/python.exe --no-deps -r github_upload/outputs/reproduction_20261118_environment/local_install.txt pytest==9.1.1 iniconfig pluggy pygments
Set-Location github_upload
& ../.venv/Scripts/python.exe -m pytest test_security.py test_exploration.py -q --basetemp outputs/reproduction_20261118_environment/pytest_tmp3 -p no:cacheprovider
& ../.venv/Scripts/python.exe check_setup.py --out outputs/reproduction_20261118_setup_numeric --no-render
& ../.venv/Scripts/python.exe check_setup.py --out outputs/reproduction_20261118_setup_render
& ../.venv/Scripts/python.exe evaluate.py --models outputs/sac_seed_3_sync/model.zip --episodes 2 --epsilons 0.1 --durations 20 --test-base 802008 --calibration-base 302000 --out outputs/reproduction_20261118_smoke
& ../.venv/Scripts/python.exe audit_results.py outputs/main_v1 --output outputs/reproduction_20261118_environment/historical_audit.json
& ../.venv/Scripts/python.exe evaluate.py --phase main --plan main_plan.json --episodes 30 --test-base 800000 --calibration-base 300000 --models outputs/sac_seed_1_sync/model.zip outputs/sac_seed_2_sync/model.zip outputs/sac_seed_3_sync/model.zip --out outputs/reproduction_20261118_main
& ../.venv/Scripts/python.exe exploration.py --out outputs/exploratory_20261118
& ../.venv/Scripts/python.exe reproduce_failure.py
& ../.venv/Scripts/python.exe audit_results.py outputs/reproduction_20261118_main --output outputs/reproduction_20261118_environment/local_audit.json
& ../.venv/Scripts/python.exe build_deliverables.py
& ../.venv/Scripts/python.exe finalize_deliverables.py
& ../.venv/Scripts/python.exe audit_exploration.py
# Final dependency compatibility correction: project-local installation only.
uv pip install --python ../.venv/Scripts/python.exe torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
& ../.venv/Scripts/python.exe -m pip check
& ../.venv/Scripts/python.exe check_setup.py --no-render --out outputs/reproduction_20261118_compatible_numeric
& ../.venv/Scripts/python.exe check_setup.py --out outputs/reproduction_20261118_compatible_render
& ../.venv/Scripts/python.exe -m pytest test_security.py test_exploration.py -q --basetemp outputs/reproduction_20261118_environment/pytest_compatible -p no:cacheprovider
& ../.venv/Scripts/python.exe evaluate.py --models outputs/sac_seed_3_sync/model.zip --episodes 2 --epsilons 0.1 --durations 20 --test-base 802008 --calibration-base 302000 --out outputs/reproduction_20261118_compatible_smoke
& ../.venv/Scripts/python.exe evaluate.py --phase main --plan main_plan.json --episodes 30 --test-base 800000 --calibration-base 300000 --models outputs/sac_seed_1_sync/model.zip outputs/sac_seed_2_sync/model.zip outputs/sac_seed_3_sync/model.zip --out outputs/reproduction_20261118_compatible_main
& ../.venv/Scripts/python.exe exploration.py --out outputs/exploratory_20261118_compatible
& ../.venv/Scripts/python.exe audit_results.py outputs/reproduction_20261118_compatible_main --output outputs/reproduction_20261118_environment/compatible_main_audit.json
& ../.venv/Scripts/python.exe audit_exploration.py --run outputs/exploratory_20261118_compatible/test --out outputs/reproduction_20261118_compatible_audit
& ../.venv/Scripts/python.exe verify_compatible.py
