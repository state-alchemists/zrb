pytest -vv \
 --cov=my_app_name \
 --cov-config=.coveragerc \
 --cov-report=html \
 --cov-report=term \
 --cov-report=term-missing \
 --ignore=_zrb
