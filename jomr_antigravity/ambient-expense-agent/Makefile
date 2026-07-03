.PHONY: install playground generate-traces grade

install:
	uv tool install google-agents-cli
	agents-cli install

playground:
	uv run python expense_agent/fast_api_app.py

generate-traces:
	uv run python tests/eval/generate_traces.py

grade:
	agents-cli eval grade --traces artifacts/traces/generated_traces.json --config tests/eval/eval_config.yaml
