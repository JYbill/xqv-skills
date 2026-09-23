```gitignore
# Local tools
mise.local.toml

# Dependencies and package manager
node_modules/
package-lock.json

# Builds and caches
dist/
.build
build/Release
.cache/
.grunt
.nar
*.nar
.es5
.lock-wscript
lib-cov
.publish

# Logs, coverage, and runtime data
*.log
npm-debug.log*
coverage/
pids
*.pid
*.seed
app_version
nul
.DS_Store

# Local environments and TLS files
.env
.env.*
!*.example
!*.sample
env/.env
env/.development.env
env/.production.env
env/tls/*
packages/api/env/.env
packages/api/env/.development.env
packages/api/env/.production.env
packages/api/env/tls/*

# Generated Prisma client; migrations remain versioned
packages/api/src/library/prisma/generate/

# Generated and local project directories
deploy
docs/apidoc/
docs/plan/
public/**/*
!public/**/
!public/**/.gitkeep
tmp/*
!tmp/.gitkeep
logs/*
!logs/.gitkeep

# Local agent state
.ai
.aiassistant
.sisyphus
.opencode
.claude/settings.local.json
.claude/worktree
.spec-workflow/
.codegraph
```
