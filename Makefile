.PHONY: demo test verify audit

demo:
	PYTHONPATH=src python3 demo.py

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v


verify:
	PYTHONPATH=src python3 demo.py --list fixtures/second_list.json

audit:
	PYTHONPATH=src python3 audit.py
