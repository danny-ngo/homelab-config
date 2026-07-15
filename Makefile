SHELL := /usr/bin/env bash
ANSIBLE := .venv/bin/ansible-playbook -i ansible/inventories/production/hosts.yml
PLAYBOOK ?= ansible/playbooks/site.yml
LIMIT ?=
PROFILE ?=
BOOTSTRAP_ARGS ?=

.PHONY: bootstrap prepare deps init-inventory inventory lint syntax test ci check apply validate idempotency phase1 phase2 dns k3s k3s-reboot-test k3s-admit-experimental
bootstrap: ; ./bootstrap.sh $(if $(PROFILE),--profile $(PROFILE)) $(if $(LIMIT),--limit $(LIMIT)) $(BOOTSTRAP_ARGS)
prepare: ; ./bootstrap.sh --prepare-only
deps: ; .venv/bin/ansible-galaxy collection install -r ansible/requirements.yml -p .ansible/collections
init-inventory: ; test -e ansible/inventories/production || cp -R ansible/inventories/example ansible/inventories/production
inventory: ; ANSIBLE_CONFIG=ansible/ansible.cfg .venv/bin/ansible-inventory --graph
lint: ; .venv/bin/yamllint . && ANSIBLE_CONFIG=ansible/ansible.cfg .venv/bin/ansible-lint ansible/playbooks
syntax: ; @for playbook in ansible/playbooks/*.yml; do \
	ANSIBLE_CONFIG=ansible/ansible.cfg .venv/bin/ansible-playbook \
		-i ansible/inventories/example/hosts.yml "$$playbook" --syntax-check || exit; \
	done
test: ; .venv/bin/python -m unittest discover -s tests -v
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
k3s-admit-experimental: ; test -n "$(LIMIT)" && $(MAKE) apply PLAYBOOK=ansible/playbooks/k3s-admit-experimental.yml LIMIT="$(LIMIT)"
