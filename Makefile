SHELL := /usr/bin/env bash
UV_RUN := uv run --frozen
UV_TOOL_BIN := $(shell uv tool dir --bin 2>/dev/null)
ANSIBLE_PLAYBOOK ?= $(if $(UV_TOOL_BIN),$(UV_TOOL_BIN)/ansible-playbook,ansible-playbook)
ANSIBLE_GALAXY ?= $(if $(UV_TOOL_BIN),$(UV_TOOL_BIN)/ansible-galaxy,ansible-galaxy)
ANSIBLE := $(ANSIBLE_PLAYBOOK) -i ansible/inventories/production/hosts.yml
PLAYBOOK ?= ansible/playbooks/site.yml
LIMIT ?=
PROFILE ?=
BOOTSTRAP_ARGS ?=

.PHONY: bootstrap prepare deps init-inventory inventory lint syntax test ci check apply validate idempotency phase1 phase2 dns k3s k3s-reboot-test pi1-sentinel pi1-probe
bootstrap: ; ./bootstrap.sh $(if $(PROFILE),--profile $(PROFILE)) $(if $(LIMIT),--limit $(LIMIT)) $(BOOTSTRAP_ARGS)
prepare: ; ./bootstrap.sh --prepare-only
deps: ; $(ANSIBLE_GALAXY) collection install -r ansible/requirements.yml -p .ansible/collections
init-inventory: ; test -e ansible/inventories/production || cp -R ansible/inventories/example ansible/inventories/production
inventory: ; ANSIBLE_CONFIG=ansible/ansible.cfg ansible-inventory --graph
lint: ; $(UV_RUN) yamllint . && ANSIBLE_CONFIG=ansible/ansible.cfg $(UV_RUN) ansible-lint ansible/playbooks
syntax: ; @for playbook in ansible/playbooks/*.yml; do \
	ANSIBLE_CONFIG=ansible/ansible.cfg $(UV_RUN) ansible-playbook \
		-i ansible/inventories/example/hosts.yml "$$playbook" --syntax-check || exit; \
	done
test: ; $(UV_RUN) python -m unittest discover -s tests -v
ci: lint syntax test
check: ; ANSIBLE_CONFIG=ansible/ansible.cfg $(ANSIBLE) $(PLAYBOOK) --check $(if $(LIMIT),--limit $(LIMIT))
apply: ; ANSIBLE_CONFIG=ansible/ansible.cfg $(ANSIBLE) $(PLAYBOOK) $(if $(LIMIT),--limit $(LIMIT))
validate: ; ANSIBLE_CONFIG=ansible/ansible.cfg $(ANSIBLE) ansible/playbooks/validate.yml $(if $(LIMIT),--limit $(LIMIT))
idempotency: ; @$(MAKE) apply PLAYBOOK=$(PLAYBOOK) LIMIT="$(LIMIT)" && $(MAKE) check PLAYBOOK=$(PLAYBOOK) LIMIT="$(LIMIT)"
phase1: ; $(MAKE) apply PLAYBOOK=ansible/playbooks/base.yml LIMIT="$(LIMIT)"
phase2: ; $(MAKE) apply PLAYBOOK=ansible/playbooks/workstations.yml LIMIT="$(LIMIT)"
dns: ; $(MAKE) apply PLAYBOOK=ansible/playbooks/dns.yml LIMIT="$(LIMIT)"
k3s: ; $(MAKE) apply PLAYBOOK=ansible/playbooks/k3s.yml LIMIT="$(LIMIT)"
k3s-reboot-test: ; test -n "$(LIMIT)" && $(MAKE) apply PLAYBOOK=ansible/playbooks/k3s.yml LIMIT="$(LIMIT)"
pi1-sentinel: ; $(MAKE) apply PLAYBOOK=ansible/playbooks/pi1-sentinel.yml LIMIT="$(LIMIT)"
pi1-probe: ; $(MAKE) apply PLAYBOOK=ansible/playbooks/pi1-probe.yml LIMIT="$(LIMIT)"
