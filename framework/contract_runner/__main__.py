"""
``python -m framework.contract_runner`` entrypoint: runs ``main_dcc`` (functional DCC contract CLI).

For performance-only runs use ``python -m framework.contract_runner.dcc.perf_cli`` or import ``main_dcc_perf``.
"""
from framework.contract_runner.dcc.cli import main_dcc

if __name__ == "__main__":
    main_dcc()
