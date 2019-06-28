.PHONY:
test:
	pytest tests


.PHONY:
lint:
	# for now, extend to other directories later
	flake8 cubes
