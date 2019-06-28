.PHONY:
test:
	pytest tests


.PHONY:
lint:
	flake8
