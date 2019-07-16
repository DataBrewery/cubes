.PHONY:
test:
	pytest tests

.PHONY:
lint:
	# for now, extend to other directories later
	flake8 cubes

.PHONY:
clean:
	find . \( -path '*/__pycache__/*' -o -name __pycache__ \) -delete


.PHONY:
format:
	isort -rc cubes
	black cubes
