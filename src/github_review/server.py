import os
from typing import Optional
from dotenv import load_dotenv
from github import Github
import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import logging
import asyncio
from asyncio import TimeoutError as AsyncTimeoutError
from github import Github
from github.GithubException import GithubException
import json
from urllib.parse import urlparse
from pydantic import AnyUrl

# 获取logger
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()
logger.info("Environment variables loaded")

# 初始化GitHub客户端和用户信息
gh_token = os.getenv("GITHUB_TOKEN")
if not gh_token:
    raise ValueError("GITHUB_TOKEN environment variable is required")
github_client = Github(gh_token)

try:
    github_user = github_client.get_user()
    github_username = github_user.login
    logger.info(f"Initialized GitHub client for user: {github_username}")
except GithubException as e:
    logger.error("Failed to initialize GitHub client", exc_info=True)
    raise

server = Server("github-review")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """列出可用的资源"""
    return [
        types.Resource(
            uri="github://my-pull-requests",
            name="My Pull Requests",
            description="List of pull requests created by the authenticated user"
        )
    ]

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """读取指定资源的内容"""
    logger.info(f"Attempting to read resource: {uri}")

    async def fetch_pull_requests():
        try:
            # 限制搜索结果数量，加快响应速度
            query_params = "is:pr is:open sort:updated"  # 按更新时间降序排序
            
            # 获取最近的PRs
            logger.debug("Searching for recent PRs...")
            created_query = f"{query_params} author:{github_username}"
            review_query = f"{query_params} review-requested:{github_username}"
            
            # 使用异步执行器并行获取PR列表
            loop = asyncio.get_event_loop()
            created_prs_future = loop.run_in_executor(None, lambda: list(github_client.search_issues(created_query)[:5]))
            review_prs_future = loop.run_in_executor(None, lambda: list(github_client.search_issues(review_query)[:5]))
            
            # 等待两个查询完成
            created_prs, review_prs = await asyncio.gather(created_prs_future, review_prs_future)
            
            logger.info(f"Found {len(created_prs)} PRs created by user")
            logger.info(f"Found {len(review_prs)} PRs requesting user's review")
            
            # 合并PR列表
            all_prs = created_prs + review_prs
            pr_list = [
                {
                    "title": pr.title,
                    "url": pr.html_url,
                    "state": pr.state,
                    "created_at": pr.created_at.isoformat(),
                    "repository": pr.repository.full_name,
                    "type": "Created by you" if pr.user.login == github_username else "Requested for review"
                }
                for pr in all_prs
            ]
            
            logger.debug(f"Successfully processed {len(pr_list)} pull requests")
            return json.dumps(pr_list, indent=2)
            
        except GithubException as e:
            logger.error(f"GitHub API error: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error fetching pull requests: {str(e)}", exc_info=True)
            raise

    try:
        if str(uri) == "github://my-pull-requests":
            return await asyncio.wait_for(fetch_pull_requests(), timeout=15.0)
        else:
            logger.warning(f"Unknown resource URI: {uri}")
            raise ValueError(f"Unknown resource URI: {uri}")
            
    except AsyncTimeoutError:
        logger.error(f"Timeout occurred while reading resource: {uri}")
        return json.dumps([], indent=2)
    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e}", exc_info=True)
        raise

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """列出可用的工具"""
    return [
        types.Tool(
            name="review-pr",
            description="Review a pull request and provide feedback",
            inputSchema={
                "type": "object",
                "properties": {
                    "pr_url": {
                        "type": "string",
                        "description": "Full PR URL (e.g. https://github.com/owner/repo/pull/1)"
                    },
                    "owner": {
                        "type": "string",
                        "description": "Repository owner"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "pr_number": {
                        "type": "integer",
                        "description": "PR number to review"
                    }
                },
                "oneOf": [
                    {"required": ["pr_url"]},
                    {"required": ["owner", "repo", "pr_number"]}
                ]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """处理工具调用"""
    if name != "review-pr" or not arguments:
        raise ValueError(f"Unknown tool or missing arguments: {name}")
    
    # 从PR URL或单独的参数中获取信息
    if "pr_url" in arguments:
        pr_url = arguments["pr_url"]
        # 解析PR URL
        path = urlparse(pr_url).path.strip("/").split("/")
        if len(path) != 4 or path[2] != "pull":
            raise ValueError(f"Invalid PR URL format: {pr_url}")
        owner = path[0]
        repo = path[1]
        pr_number = int(path[3])
    else:
        owner = arguments["owner"]
        repo = arguments["repo"]
        pr_number = arguments["pr_number"]
    
    # 获取PR信息
    repo = github_client.get_repo(f"{owner}/{repo}")
    pr = repo.get_pull(pr_number)
    
    # 获取reviews
    reviews = []
    for review in pr.get_reviews():
        reviews.append({
            "user": review.user.login,
            "state": review.state,
            "body": review.body,
            "submitted_at": review.submitted_at.isoformat() if review.submitted_at else None
        })

    # 获取PR comments (issue级别评论)
    comments = []
    for comment in pr.get_issue_comments():
        comments.append({
            "user": comment.user.login,
            "body": comment.body,
            "created_at": comment.created_at.isoformat()
        })

    # 获取review comments (代码行级别评论)
    review_comments = []
    for comment in pr.get_comments():
        review_comments.append({
            "user": comment.user.login,
            "body": comment.body,
            "created_at": comment.created_at.isoformat(),
            "path": comment.path,
            "position": comment.position,
            "commit_id": comment.commit_id
        })

    # 收集PR的所有相关信息
    files = pr.get_files()
    changes = []
    for file in files:
        changes.append({
            "filename": file.filename,
            "status": file.status,
            "additions": file.additions,
            "deletions": file.deletions,
            "changes": file.changes,
            "patch": file.patch
        })

    # 修改返回格式
    return [types.TextContent(
        type="text",
        text=json.dumps({
            "pr_info": {
                "title": pr.title,
                "body": pr.body,
                "changed_files": len(changes),
                "additions": pr.additions,
                "deletions": pr.deletions,
                "reviews": reviews,
                "comments": comments,
                "review_comments": review_comments
            },
            "changes": changes
        }, indent=2)
    )]

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    return [
        types.Prompt(
            name="code-style-review",
            description="Review PR focusing on code style and conventions",
            arguments=[
                types.PromptArgument(
                    name="pr_url",
                    description="PR URL to review",
                    required=True
                )
            ]
        ),
        types.Prompt(
            name="security-review", 
            description="Review PR for security issues",
            arguments=[
                types.PromptArgument(
                    name="pr_url",
                    description="PR URL to review",
                    required=True
                )
            ]
        )
    ]

@server.progress_notification()
async def handle_progress(progress_token: str | int, progress: float, message: str | None = None) -> None:
    """处理���度通知"""
    logger.info(f"Progress update - token: {progress_token}, progress: {progress:.2%}, message: {message or 'N/A'}")

async def main():
    """行服务器"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="github-review",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(resources_changed=True, tools_changed=True, prompts_changed=True),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())