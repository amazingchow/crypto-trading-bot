include .env
export

VERSION      := v1.0.0
GIT_HASH     := $(shell git rev-parse --short HEAD)

.PHONY: help
help: ### Display this help screen.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: deps
deps: ### Package the runtime requirements.
	@pip freeze > requirements.txt

.PHONY: lint
lint: ### Lint code.
	@pyflakes internal/*/*.py
	@pycodestyle internal/*/*.py --ignore=E402,E501,W293,E266

.PHONY: ### Run code.
run:
	@python bot.py
