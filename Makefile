all: output/members-v3.json output/members-v4.json

diff: all
	diff -w output/members-v*

clean:
	rm -rf output

venv:
	virtualenv venv
	./venv/bin/pip install -r requirements.txt

output/members-v3.json: venv
	@mkdir -p output
	./venv/bin/python fetch-team-members-v3.py

output/members-v4.json: venv
	@mkdir -p output
	./venv/bin/python fetch-team-members-v4.py
