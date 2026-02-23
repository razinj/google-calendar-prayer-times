run:
	poetry run python src/script.py

run-de:
	poetry run python src/script.py --country de

run-ma:
	poetry run python src/script.py --country ma

run-dry:
	poetry run python src/script.py --dry-run

run-dry-de:
	poetry run python src/script.py --country de --dry-run

run-dry-ma:
	poetry run python src/script.py --country ma --dry-run

format:
	poetry run black .
	poetry run isort .

lint:
	poetry run mypy .
	poetry run flake8 .

format-ci:
	poetry run black . --check
	poetry run isort . --check

lint-ci:
	poetry run mypy .
	poetry run flake8 .

test:
	PYTHONPATH=. poetry run pytest -v
