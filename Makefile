.PHONY: all starter full anomalous test repro clean

PYTHON = python

all: starter full anomalous

starter:
	$(PYTHON) -m schedgen --profile starter --out data/starter

full:
	$(PYTHON) -m schedgen --profile full --out data/full

anomalous:
	$(PYTHON) -m schedgen --profile full --out data/anomalous --anomalies

test:
	pytest tests/ -v

repro:
	@echo "=== Run 1 ==="
	$(PYTHON) -m schedgen --profile starter --out data/repro_run1
	@echo "=== Run 2 ==="
	$(PYTHON) -m schedgen --profile starter --out data/repro_run2
	$(PYTHON) -c "\
import hashlib, pathlib, sys; \
def cs(d): return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(pathlib.Path(d).glob('*.csv'))}; \
a,b = cs('data/repro_run1'), cs('data/repro_run2'); \
diff = {k for k in a if a[k]!=b.get(k)}; \
print('PASS: checksums match' if not diff else f'FAIL: {diff}'); \
sys.exit(0 if not diff else 1)"

clean:
	rm -rf data/starter data/full data/anomalous data/repro_run1 data/repro_run2
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
