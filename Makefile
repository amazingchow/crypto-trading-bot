include .env
export

VERSION  := v1.0.0
GIT_HASH := $(shell git rev-parse --short HEAD)
SERVICE  := crypto-trading-bot
CURR_DIR := $(shell pwd)

.PHONY: help
help: ### Display this help screen.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: deps
deps: ### Package the runtime requirements.
	@pip freeze > requirements.txt

.PHONY: yaml_fmt
yaml_fmt:
	@yamlfmt docker-compose.yml

.PHONY: lint
lint: ### Lint code.
	@pyflakes run_grid_trading_bot.py
	@pyflakes run_stagging_bot.py
	@pyflakes internal/*/*.py
	@pycodestyle run_grid_trading_bot.py --ignore=W293,W503,E266,E402,E501
	@pycodestyle run_stagging_bot.py --ignore=W293,W503,E266,E402,E501
	@pycodestyle internal/*/*.py --ignore=W293,W503,E266,E402,E501

.PHONY: run_compose
run_compose:
	@(docker-compose -f "${CURR_DIR}/docker-compose.yml" up -d --build)

.PHONY: shutdown_compose
shutdown_compose:
	@(docker-compose -f "${CURR_DIR}/docker-compose.yml" down)
