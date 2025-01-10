run:
	poetry run python src/script.py

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
