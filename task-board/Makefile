.PHONY: check-clean version-patch version-minor version-major

# Target name minus the prefix.
BUMP = $(@:version-%=%)
PLUGIN_JSON = .claude-plugin/plugin.json

check-clean:
	@test -z "$$(git status --porcelain)" || { echo "Git tree is dirty."; exit 1; }

version-patch version-minor version-major: check-clean
	@npm version $(BUMP) --no-git-tag-version > /dev/null && \
	NEW_VERSION=$$(jq -r .version package.json) && \
	jq --arg version "$$NEW_VERSION" '.version = $$version' $(PLUGIN_JSON) > $(PLUGIN_JSON).tmp && \
	mv $(PLUGIN_JSON).tmp $(PLUGIN_JSON) && \
	git add package.json $(PLUGIN_JSON) && \
	git commit -q -m "task-board v$$NEW_VERSION"
