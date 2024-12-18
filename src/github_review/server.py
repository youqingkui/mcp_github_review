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

# @server.list_resources()
# async def handle_list_resources() -> list[types.Resource]:
#     """列出可用的资源类型，设置5秒超时"""
#     resources = []
    
#     async def fetch_prs():
#         try:
#             # 限制搜索结果数量，加快响应速度
#             query_params = "is:pr is:open sort:updated"  # 按更新时间排序
            
#             # 获取最近的PRs
#             logger.debug("Searching for recent PRs...")
#             created_query = f"{query_params} author:{github_username}"
#             review_query = f"{query_params} review-requested:{github_username}"
            
#             # 限制每种类型最多获取5个最近的PRs
#             created_prs = list(github_client.search_issues(created_query)[:5])
#             logger.info(f"Found {len(created_prs)} recent PRs created by user")
            
#             review_prs = list(github_client.search_issues(review_query)[:5])
#             logger.info(f"Found {len(review_prs)} recent PRs requesting user's review")
            
#             # 合并并处理PRs
#             all_prs = created_prs + review_prs
#             logger.debug(f"Processing {len(all_prs)} total PRs...")
            
#             for issue in all_prs:
#                 pr_repo = issue.repository
#                 base_uri = f"pr://{pr_repo.owner.login}/{pr_repo.name}/{issue.number}"
#                 pr_type = "Created by you" if issue.user.login == github_username else "Requested for review"
                
#                 # 只添加基本信息资源，其他资源按需获取
#                 resources.append(types.Resource(
#                     uri=f"{base_uri}",
#                     name=f"PR #{issue.number}: {issue.title}",
#                     description=f"[{pr_type}] in {pr_repo.full_name}"
#                 ))
            
#             logger.info(f"Successfully created {len(resources)} resources")
#             return resources
            
#         except GithubException as e:
#             logger.error(f"GitHub API error: {str(e)}", exc_info=True)
#             raise
#         except Exception as e:
#             logger.error(f"Error listing resources: {str(e)}", exc_info=True)
#             raise

#     try:
#         # 设置5秒超时
#         return await asyncio.wait_for(fetch_prs(), timeout=5.0)
#     except AsyncTimeoutError:
#         logger.warning("List resources operation timed out after 5 seconds")
#         # 如果超时，返回已经获取到的资源
#         return resources if resources else []
#     except Exception as e:
#         logger.error(f"Unexpected error: {str(e)}", exc_info=True)
#         raise

# @server.read_resource()
# async def handle_read_resource(uri: AnyUrl) -> str:
#     """读取资源内容"""
#     try:
#         uri_str = str(uri)
#         logger.info(f"Reading resource: {uri_str}")
        
#         # 解析URI
#         parts = uri_str.split("/")
#         if not uri_str.startswith("pr://") or len(parts) < 5:
#             logger.error(f"Invalid PR URI format: {uri_str}")
#             raise ValueError(f"Invalid PR URI: {uri_str}")
        
#         owner = parts[2]
#         repo = parts[3]
#         pr_number = int(parts[4])
#         resource_type = parts[5] if len(parts) > 5 else "info"
        
#         logger.debug(f"Parsed URI - owner: {owner}, repo: {repo}, PR: {pr_number}, type: {resource_type}")
        
#         # 获取PR
#         repo = github_client.get_repo(f"{owner}/{repo}")
#         pr = repo.get_pull(pr_number)
#         logger.debug(f"Successfully retrieved PR #{pr_number} from {owner}/{repo}")
        
#         if resource_type == "info":
#             logger.debug("Fetching PR basic information")
#             content = {
#                 "title": pr.title,
#                 "body": pr.body,
#                 "state": pr.state,
#                 "created_at": pr.created_at.isoformat(),
#                 "updated_at": pr.updated_at.isoformat(),
#                 "head": pr.head.ref,
#                 "base": pr.base.ref,
#                 "mergeable": pr.mergeable
#             }
#             return json.dumps(content, indent=2)
            
#         elif resource_type == "diff":
#             logger.debug("Fetching PR diff content")
#             files = pr.get_files()
#             content = []
#             for file in files:
#                 content.append({
#                     "filename": file.filename,
#                     "status": file.status,
#                     "additions": file.additions,
#                     "deletions": file.deletions,
#                     "changes": file.changes,
#                     "patch": file.patch
#                 })
#             return json.dumps(content, indent=2)
            
#         elif resource_type == "comments":
#             logger.debug("Fetching PR comments")
#             comments = []
#             for comment in pr.get_comments():
#                 comments.append({
#                     "user": comment.user.login,
#                     "body": comment.body,
#                     "created_at": comment.created_at.isoformat(),
#                     "path": comment.path,
#                     "position": comment.position
#                 })
#             logger.debug(f"Found {len(comments)} comments")
#             return json.dumps(comments, indent=2)
            
#         else:
#             logger.error(f"Unknown resource type: {resource_type}")
#             raise ValueError(f"Unknown resource type: {resource_type}")
            
#     except Exception as e:
#         logger.error(f"Error reading resource: {str(e)}", exc_info=True)
#         raise

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

async def main():
    """运行服务器"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="github-review",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())