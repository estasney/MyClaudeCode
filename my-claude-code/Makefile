.PHONY: check-clean version-patch version-minor version-major

# Target name minus the prefix.
BUMP = $(@:version-%=%)
PLUGIN_JSON = .claude-plugin/plugin.json

check-clean:
	@test -z "$$(git status --porcelain)" || { echo "Git tree is dirty."; exit 1; }

version-patch version-minor version-major: check-clean
	@jq --arg bump $(BUMP) '.version |= (split(".") | map(tonumber) | if $$bump == "major" then [.[0] + 1, 0, 0] elif $$bump == "minor" then [.[0], .[1] + 1, 0] else [.[0], .[1], .[2] + 1] end | map(tostring) | join("."))' $(PLUGIN_JSON) > $(PLUGIN_JSON).tmp && \
	mv $(PLUGIN_JSON).tmp $(PLUGIN_JSON) && \
	NEW_VERSION=$$(jq -r .version $(PLUGIN_JSON)) && \
	git add $(PLUGIN_JSON) && \
	git commit -q -m "my-claude-code v$$NEW_VERSION"
