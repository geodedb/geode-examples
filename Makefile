# Geode Examples - Makefile
#
# Build, test, and verification orchestration for Geode examples and claim verification.
#
# Usage:
#   make setup      - Set up local development environment
#   make test       - Run all tests
#   make benchmark  - Run performance benchmarks
#   make verify     - Run full claim verification
#   make report     - Generate verification report
#   make clean      - Clean up environment

.PHONY: all setup build test test-gql test-clients test-features test-security \
        benchmark benchmark-throughput benchmark-latency benchmark-vector \
        benchmark-standard benchmark-full benchmark-extreme benchmark-scale \
        benchmark-hightp-quick benchmark-hightp-standard benchmark-hightp-intensive benchmark-hightp-max \
        benchmark-multi-cli benchmark-multi-go benchmark-multi-rust benchmark-multi-zig \
        benchmark-multi-nodejs benchmark-multi-python benchmark-multi-native benchmark-multi-all benchmark-multi-intensive \
        benchmark-bare-quick benchmark-bare-standard benchmark-bare-intensive benchmark-bare-multi benchmark-bare-max \
        benchmark-stats-quick benchmark-stats-standard benchmark-stats-publication benchmark-stats-intensive \
        production-up production-up-monitoring production-down production-logs \
        production-status production-shell setup-server \
        verify verify-claims verify-canary \
        report clean help

# Configuration
DOCKER_COMPOSE ?= docker compose
GEODE_HOST ?= localhost:3141
REPORTS_DIR ?= reports
PUBLIC_DIR ?= public
PYTHON ?= python3

# Default target
all: setup test verify report

##@ Setup

setup: ## Set up local development environment
	@echo "Setting up Geode Examples environment..."
	@chmod +x scripts/*.sh
	@./scripts/setup.sh

setup-monitoring: ## Set up with monitoring stack
	@./scripts/setup.sh --with-monitoring

setup-full: ## Set up with all optional services
	@./scripts/setup.sh --with-monitoring --with-kafka

##@ Build

build: build-docker ## Build all components

build-docker: ## Build Docker images
	@echo "Building Docker images..."
	$(DOCKER_COMPOSE) build

build-clients: build-go build-python build-rust build-zig ## Build all client examples

build-go: ## Build Go client examples
	@if [ -f clients/go/go.mod ]; then \
		cd clients/go && go build ./...; \
	fi

build-python: ## Install Python dependencies
	@if [ -f clients/python/requirements.txt ]; then \
		pip install -r clients/python/requirements.txt; \
	fi

build-rust: ## Build Rust client examples
	@if [ -f clients/rust/Cargo.toml ]; then \
		cd clients/rust && cargo build; \
	fi

build-zig: ## Build Zig client examples
	@if [ -f clients/zig/build.zig ]; then \
		cd clients/zig && zig build; \
	fi

##@ Testing

test: test-gql test-clients test-features ## Run all tests

test-quick: ## Run quick smoke tests
	@./scripts/run_all_tests.sh --quick

test-gql: ## Run GQL compliance tests
	@echo "Running GQL tests..."
	@./scripts/run_all_tests.sh --category gql

test-clients: ## Run client library tests
	@echo "Running client tests..."
	@./scripts/run_all_tests.sh --category clients

test-features: ## Run feature verification tests
	@echo "Running feature tests..."
	@./scripts/run_all_tests.sh --category features

test-security: ## Run security verification tests
	@echo "Running security tests..."
	@./scripts/run_all_tests.sh --category security

test-performance: ## Run performance verification tests
	@echo "Running performance tests..."
	@./scripts/run_all_tests.sh --category performance

##@ Benchmarks

benchmark: benchmark-throughput benchmark-latency ## Run all benchmarks

benchmark-throughput: ## Run throughput benchmarks
	@echo "Running throughput benchmarks..."
	@mkdir -p $(REPORTS_DIR)
	@if [ -f benchmarks/load-tests/read_only.py ]; then \
		python benchmarks/load-tests/read_only.py \
			--host $(GEODE_HOST) \
			--output $(REPORTS_DIR)/throughput-read-only.json; \
	fi

benchmark-latency: ## Run latency benchmarks
	@echo "Running latency benchmarks..."
	@mkdir -p $(REPORTS_DIR)
	@if [ -f benchmarks/load-tests/vector_distance.py ]; then \
		python benchmarks/load-tests/vector_distance.py \
			--host $(GEODE_HOST) \
			--output $(REPORTS_DIR)/latency-vector.json; \
	fi

benchmark-vector: ## Run vector search benchmarks
	@echo "Running vector search benchmarks..."
	@mkdir -p $(REPORTS_DIR)

benchmark-scale: ## Run scalability tests (long running)
	@echo "Running scalability tests..."
	@echo "Warning: This may take several hours"

benchmark-standard: ## Run standard CI/CD benchmark (100K nodes, 100 connections)
	@echo "Running standard benchmark profile..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/data-generators/scale_test.py \
		--nodes 100000 \
		--rels-per-node 5 \
		--batch-size 5000 \
		--output $(REPORTS_DIR)/scale_standard.json
	@$(PYTHON) benchmarks/load-tests/read_only.py \
		--workers 100 \
		--duration 300 \
		--output $(REPORTS_DIR)/perf_standard_read.json
	@$(PYTHON) benchmarks/load-tests/concurrent_connections.py \
		--target 100 \
		--batch-size 10 \
		--output $(REPORTS_DIR)/perf_standard_conn.json

benchmark-full: ## Run full benchmark (1M nodes, 1K connections) - 30+ min
	@echo "Running full benchmark profile..."
	@echo "Warning: This will take 30+ minutes"
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/data-generators/scale_test.py \
		--nodes 1000000 \
		--rels-per-node 5 \
		--batch-size 10000 \
		--output $(REPORTS_DIR)/scale_full.json
	@$(PYTHON) benchmarks/load-tests/read_only.py \
		--workers 100 \
		--duration 600 \
		--output $(REPORTS_DIR)/perf_full_read.json
	@$(PYTHON) benchmarks/load-tests/concurrent_connections.py \
		--target 1000 \
		--batch-size 50 \
		--output $(REPORTS_DIR)/perf_full_conn.json

benchmark-extreme: ## Run extreme benchmark (100M nodes, 10K connections) - 24+ hours
	@echo "Running extreme benchmark profile..."
	@echo "Warning: This requires significant resources and may take 24+ hours"
	@echo "Recommended: 256GB+ RAM, 32+ cores, 2TB+ NVMe SSD"
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/data-generators/scale_test.py \
		--nodes 100000000 \
		--rels-per-node 10 \
		--batch-size 50000 \
		--output $(REPORTS_DIR)/scale_extreme.json
	@$(PYTHON) benchmarks/load-tests/read_only.py \
		--workers 1000 \
		--duration 3600 \
		--output $(REPORTS_DIR)/perf_extreme_read.json
	@$(PYTHON) benchmarks/load-tests/concurrent_connections.py \
		--target 10000 \
		--batch-size 500 \
		--output $(REPORTS_DIR)/perf_extreme_conn.json

##@ High-Throughput Benchmarks

benchmark-hightp-quick: ## Quick high-throughput test (30s, 20 workers)
	@echo "Running quick high-throughput benchmark..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/high_throughput.py \
		--workers 20 \
		--duration 30 \
		--batch-size 10 \
		--output $(REPORTS_DIR)/hightp_quick.json

benchmark-hightp-standard: ## Standard high-throughput test (60s, 50 workers)
	@echo "Running standard high-throughput benchmark..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/high_throughput.py \
		--workers 50 \
		--duration 60 \
		--batch-size 20 \
		--output $(REPORTS_DIR)/hightp_standard.json

benchmark-hightp-intensive: ## Intensive high-throughput test (300s, 100 workers)
	@echo "Running intensive high-throughput benchmark..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/high_throughput.py \
		--workers 100 \
		--duration 300 \
		--batch-size 50 \
		--output $(REPORTS_DIR)/hightp_intensive.json

benchmark-hightp-max: ## Maximum high-throughput test (600s, 200 workers, 100 batch)
	@echo "Running maximum high-throughput benchmark..."
	@echo "Warning: This is a stress test and may require significant resources"
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/high_throughput.py \
		--workers 200 \
		--duration 600 \
		--batch-size 100 \
		--output $(REPORTS_DIR)/hightp_max.json

##@ Multi-Client Benchmarks

benchmark-multi-cli: ## CLI-only baseline benchmark (50 workers)
	@echo "Running CLI-only baseline benchmark..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients cli \
		--workers 50 \
		--duration 60 \
		--batch-size 20 \
		--output $(REPORTS_DIR)/multi_cli.json

benchmark-multi-go: ## Go client benchmark (30 workers)
	@echo "Running Go client benchmark..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients go \
		--workers 30 \
		--duration 60 \
		--batch-size 10 \
		--output $(REPORTS_DIR)/multi_go.json

benchmark-multi-rust: ## Rust client benchmark (30 workers)
	@echo "Running Rust client benchmark..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients rust \
		--workers 30 \
		--duration 60 \
		--batch-size 10 \
		--output $(REPORTS_DIR)/multi_rust.json

benchmark-multi-zig: ## Zig client benchmark (30 workers)
	@echo "Running Zig client benchmark..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients zig \
		--workers 30 \
		--duration 60 \
		--batch-size 10 \
		--output $(REPORTS_DIR)/multi_zig.json

benchmark-multi-nodejs: ## Node.js client benchmark (30 workers)
	@echo "Running Node.js client benchmark..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients nodejs \
		--workers 30 \
		--duration 60 \
		--batch-size 10 \
		--output $(REPORTS_DIR)/multi_nodejs.json

benchmark-multi-python: ## Python client benchmark (30 workers)
	@echo "Running Python client benchmark..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients python \
		--workers 30 \
		--duration 60 \
		--batch-size 10 \
		--output $(REPORTS_DIR)/multi_python.json

benchmark-multi-native: ## Native clients benchmark (Go, Rust, Zig - 20 workers each)
	@echo "Running native clients benchmark..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients go,rust,zig \
		--workers 20 \
		--duration 60 \
		--batch-size 10 \
		--output $(REPORTS_DIR)/multi_native.json

##@ Bare-Metal Benchmarks (No Docker)
# These targets run benchmarks directly against a local/remote Geode server
# without Docker overhead. Requires geode server running and accessible.
# Set GEODE_HOST to target a specific server (default: localhost:3141)
# Set GEODE_BIN to specify geode CLI path (default: geode)

GEODE_BIN ?= geode

benchmark-bare-quick: ## Quick bare-metal test (30s, 50 workers, single client)
	@echo "Running quick bare-metal benchmark..."
	@echo "Target: $(GEODE_HOST)"
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients cli \
		--workers 50 \
		--duration 30 \
		--batch-size 20 \
		--no-docker \
		--geode-path $(GEODE_BIN) \
		--host $(firstword $(subst :, ,$(GEODE_HOST))) \
		--port $(lastword $(subst :, ,$(GEODE_HOST))) \
		--output $(REPORTS_DIR)/bare_quick.json

benchmark-bare-standard: ## Standard bare-metal benchmark (60s, 100 workers)
	@echo "Running standard bare-metal benchmark..."
	@echo "Target: $(GEODE_HOST)"
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients cli \
		--workers 100 \
		--duration 60 \
		--batch-size 50 \
		--no-docker \
		--geode-path $(GEODE_BIN) \
		--host $(firstword $(subst :, ,$(GEODE_HOST))) \
		--port $(lastword $(subst :, ,$(GEODE_HOST))) \
		--output $(REPORTS_DIR)/bare_standard.json

benchmark-bare-intensive: ## Intensive bare-metal benchmark (120s, 200 workers, 5 clients)
	@echo "Running intensive bare-metal benchmark..."
	@echo "Target: $(GEODE_HOST)"
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients go,python,rust,zig,nodejs \
		--workers 200 \
		--duration 120 \
		--batch-size 100 \
		--no-docker \
		--geode-path $(GEODE_BIN) \
		--host $(firstword $(subst :, ,$(GEODE_HOST))) \
		--port $(lastword $(subst :, ,$(GEODE_HOST))) \
		--output $(REPORTS_DIR)/bare_intensive.json

benchmark-bare-multi: ## Multi-client bare-metal benchmark (5 clients, 50 workers each)
	@echo "Running multi-client bare-metal benchmark..."
	@echo "Target: $(GEODE_HOST)"
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients go,python,rust,zig,nodejs \
		--workers 50 \
		--duration 60 \
		--batch-size 20 \
		--no-docker \
		--geode-path $(GEODE_BIN) \
		--host $(firstword $(subst :, ,$(GEODE_HOST))) \
		--port $(lastword $(subst :, ,$(GEODE_HOST))) \
		--output $(REPORTS_DIR)/bare_multi.json

benchmark-bare-max: ## Maximum bare-metal stress test (300s, 500 workers, 5 clients)
	@echo "Running maximum bare-metal stress test..."
	@echo "Target: $(GEODE_HOST)"
	@echo "Warning: This is a stress test - ensure server can handle load"
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients go,python,rust,zig,nodejs \
		--workers 500 \
		--duration 300 \
		--batch-size 100 \
		--no-docker \
		--geode-path $(GEODE_BIN) \
		--host $(firstword $(subst :, ,$(GEODE_HOST))) \
		--port $(lastword $(subst :, ,$(GEODE_HOST))) \
		--output $(REPORTS_DIR)/bare_max.json

benchmark-multi-all: ## All clients in parallel (10 workers each)
	@echo "Running all-clients benchmark..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients all \
		--workers 10 \
		--duration 60 \
		--batch-size 10 \
		--output $(REPORTS_DIR)/multi_all.json

benchmark-multi-intensive: ## Intensive multi-client test (all clients, 30 workers each, 120s)
	@echo "Running intensive multi-client benchmark..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) benchmarks/load-tests/multi_client_benchmark.py \
		--clients cli,go,rust,zig,python,nodejs \
		--workers 30 \
		--duration 120 \
		--batch-size 20 \
		--output $(REPORTS_DIR)/multi_intensive.json

##@ Statistical Benchmarks (Publication-Ready)

benchmark-stats-quick: ## Quick statistical benchmark (3 runs, 30s each)
	@echo "Running quick statistical benchmark..."
	@mkdir -p $(REPORTS_DIR)/benchmark
	@$(PYTHON) benchmarks/load-tests/benchmark_framework.py \
		--runs 3 \
		--workers 20 \
		--duration 30 \
		--output-dir $(REPORTS_DIR)/benchmark

benchmark-stats-standard: ## Standard statistical benchmark (5 runs, 60s each)
	@echo "Running standard statistical benchmark..."
	@mkdir -p $(REPORTS_DIR)/benchmark
	@$(PYTHON) benchmarks/load-tests/benchmark_framework.py \
		--runs 5 \
		--workers 50 \
		--duration 60 \
		--output-dir $(REPORTS_DIR)/benchmark

benchmark-stats-publication: ## Publication-quality benchmark (10 runs, 120s each)
	@echo "Running publication-quality statistical benchmark..."
	@echo "This will produce statistically significant results for publication"
	@mkdir -p $(REPORTS_DIR)/benchmark
	@$(PYTHON) benchmarks/load-tests/benchmark_framework.py \
		--runs 10 \
		--workers 100 \
		--duration 120 \
		--batch-size 20 \
		--output-dir $(REPORTS_DIR)/benchmark

benchmark-stats-intensive: ## Intensive statistical benchmark (10 runs, 300s each, 200 workers)
	@echo "Running intensive statistical benchmark..."
	@echo "Warning: This will take a significant amount of time"
	@mkdir -p $(REPORTS_DIR)/benchmark
	@$(PYTHON) benchmarks/load-tests/benchmark_framework.py \
		--runs 10 \
		--workers 200 \
		--duration 300 \
		--batch-size 50 \
		--output-dir $(REPORTS_DIR)/benchmark

##@ Production Deployment

production-up: ## Start Geode with production settings
	$(DOCKER_COMPOSE) -f docker/docker-compose.production.yml up -d

production-up-monitoring: ## Start Geode with production settings and monitoring
	$(DOCKER_COMPOSE) -f docker/docker-compose.production.yml --profile monitoring up -d

production-down: ## Stop production Geode
	$(DOCKER_COMPOSE) -f docker/docker-compose.production.yml down

production-logs: ## Follow production Geode logs
	$(DOCKER_COMPOSE) -f docker/docker-compose.production.yml logs -f geode

production-status: ## Show production service status
	$(DOCKER_COMPOSE) -f docker/docker-compose.production.yml ps

production-shell: ## Open shell in production container
	$(DOCKER_COMPOSE) -f docker/docker-compose.production.yml exec geode /bin/sh

setup-server: ## Setup bare metal server for production (requires sudo)
	@echo "Setting up production server..."
	@sudo ./scripts/setup_production_server.sh

##@ Verification

verify: verify-claims verify-canary ## Run full verification

verify-claims: ## Verify all documented claims
	@echo "Verifying documented claims..."
	@./scripts/run_all_tests.sh

verify-verbose: ## Verify with verbose output
	@./scripts/run_all_tests.sh --verbose

verify-quick: ## Quick verification (skip performance tests)
	@./scripts/run_all_tests.sh --quick

verify-canary: ## Cross-reference with CANARY markers
	@echo "Cross-referencing CANARY markers..."
	@./scripts/compare_canary.sh

extract-claims: ## Extract claims from documentation
	@echo "Extracting claims from documentation..."
	@./scripts/extract_all_claims.sh

##@ Reporting

report: report-json report-html report-badge ## Generate all reports

report-json: ## Generate JSON verification report
	@./scripts/generate_report.sh --json

report-html: ## Generate HTML verification report
	@./scripts/generate_report.sh --html

report-badge: ## Generate verification badge
	@./scripts/generate_report.sh --badge

##@ Docker

up: ## Start Geode server
	$(DOCKER_COMPOSE) up -d geode

down: ## Stop all services
	$(DOCKER_COMPOSE) down

logs: ## Follow Geode logs
	$(DOCKER_COMPOSE) logs -f geode

shell: ## Open Geode shell
	$(DOCKER_COMPOSE) exec geode geode shell

status: ## Show service status
	$(DOCKER_COMPOSE) ps

##@ Helm

helm-lint: ## Lint Helm charts
	@helm lint helm/geode
	@helm lint helm/geode-cluster 2>/dev/null || true

helm-template: ## Template Helm chart (dry-run)
	@helm template geode helm/geode

helm-install: ## Install Geode via Helm (requires K8s cluster)
	@helm install geode helm/geode

helm-upgrade: ## Upgrade Geode Helm release
	@helm upgrade geode helm/geode

helm-uninstall: ## Uninstall Geode Helm release
	@helm uninstall geode

##@ Cleanup

clean: ## Clean up environment
	@echo "Cleaning up..."
	$(DOCKER_COMPOSE) down -v --remove-orphans
	rm -rf $(REPORTS_DIR)/*
	rm -rf $(PUBLIC_DIR)/*

clean-docker: ## Remove Docker images
	docker rmi registry.gitlab.com/devnw/codepros/geode/geode:latest 2>/dev/null || true
	docker rmi geode-benchmark:latest 2>/dev/null || true
	docker rmi geode-test-harness:latest 2>/dev/null || true

clean-all: clean clean-docker ## Full cleanup including images

##@ CI/CD

ci: build test verify report ## Run full CI pipeline
	@echo "CI pipeline complete"

ci-quick: build test-quick ## Run quick CI checks
	@echo "Quick CI checks complete"

##@ Help

help: ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help
