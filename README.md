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

## Usage

Run the server:
```bash
uv run github-review
```

## Features

- Review GitHub pull requests
- Get PR summaries
- View PR comments and review history
- Analyze code changes 