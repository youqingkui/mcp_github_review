# GitHub PR Review MCP

A Model Context Protocol (MCP) server for reviewing GitHub pull requests.

## Setup

1. Clone the repository
2. Create virtual environment:
```bash
uv venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
uv pip install -e .
```

4. Copy `.env.example` to `.env` and add your GitHub token:
```bash
cp .env.example .env
# Edit .env with your GitHub token
```

## Connect to Claude Desktop

1. Install [Claude Desktop](https://claude.ai/download)

2. Configure Claude Desktop to use this MCP server. Edit the configuration file:

MacOS:
```bash
code ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Windows:
```bash
code %AppData%\Claude\claude_desktop_config.json
```

3. Add the server configuration:
```json
# Start of Selection
{
    "mcpServers": {
        "github-review": {
            "command": "uv",
            "args": [
                "--directory",
                "/ABSOLUTE/PATH/TO/github-review-mcp",  # Replace with your project's absolute path
                "run",
                "github-review"
            ],
            "env": {
                "GITHUB_TOKEN": "your_github_token_here"  # Replace with your GitHub token
            }
        }
    }
}
# End of Selection
```

4. Restart Claude Desktop

## Development and Testing

Use MCP Inspector for development and testing:
```bash
# Test the server using Inspector
npx @modelcontextprotocol/inspector uv run github-review
```

The Inspector provides:
- Interactive testing of tools and prompts
- Real-time logs and debugging information
- Request/response inspection
- Server connection status

## Features

- Review GitHub pull requests
- Get PR summaries
- View PR comments and review history
- Analyze code changes

## Usage

In Claude Desktop:

1. Using tools:
```
Could you help me review this pull request: https://github.com/owner/repo/pull/123
```

2. Using prompts:
```
/code-review https://github.com/owner/repo/pull/123
/summarize-pr https://github.com/owner/repo/pull/123
```