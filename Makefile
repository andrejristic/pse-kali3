# PSE-Kali — common tasks
.PHONY: test selftest run run-exec monitor lab-up lab-down clean

test:                ## run the full offline test suite (unit + integration)
	@for t in tests/test_kernel.py tests/test_operator.py tests/test_adapters.py \
	          tests/test_live.py tests/test_report.py tests/demo_tandem.py \
	          tests/test_integration.py; do \
	  echo "== $$t =="; python3 $$t | tail -1; done

fetch:               ## download a local GGUF model (default 7b) — see fetch_model.sh
	./fetch_model.sh 7b

selftest:            ## check the configured backend emits valid actions
	python3 run_engagement.py --config config.yaml --selftest

run:                 ## run an engagement (simulated tools)
	python3 run_engagement.py --config config.yaml

run-exec:            ## run an engagement with REAL tools against the lab
	python3 run_engagement.py --config config.yaml --execute

monitor:             ## rebuild the HTML monitor snapshot from the audit log
	python3 monitor/build_monitor.py

monitor-live:        ## serve the live monitor in a browser (polls the audit log)
	python3 monitor/serve_monitor.py

monitor-qt:          ## native desktop monitor (PySide6, no browser)
	python3 monitor/pse_monitor_qt.py

lab-up:              ## bring up the self-contained lab target
	docker compose -f lab/docker-compose.yml up -d --build

lab-down:            ## tear down the lab target
	docker compose -f lab/docker-compose.yml down

clean:
	rm -f audit/*.jsonl monitor/pse_monitor.html
