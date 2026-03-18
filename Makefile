.PHONY: install test

install:
	./setup

test:
	python3 -m unittest discover -s tests -v
