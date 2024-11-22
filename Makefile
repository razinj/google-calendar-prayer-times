format:
	black .
	isort .

lint:
	mypy .
	flake8 .

format-ci:
	black . --check
	isort . --check

lint-ci:
	mypy .
	flake8 .
