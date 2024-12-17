import os
import logging
from typing import Any, Optional
import asyncio
from github import Github
from dotenv import load_dotenv
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# 获取logger
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()
logger.info("Environment variables loaded")

# 初始化GitHub客户端
github_token = os.getenv("GITHUB_TOKEN")
if not github_token:
    logger.error("GITHUB_TOKEN not found in environment variables")
    raise ValueError("GITHUB_TOKEN environment variable is required")

g = Github(github_token)
logger.info("GitHub client initialized")

# 创建服务器实例
server = Server("github-review")
logger.info("MCP server instance created with prompts capability")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """列出可用工具"""
    logger.debug("Listing available tools")
    return [
        types.Tool(
            name="review-pr",
            description="Review a GitHub pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pr_url": {
                        "type": "string",
                        "description": "GitHub PR URL (e.g. https://github.com/owner/repo/pull/123)",
                    }
                },
                "required": ["pr_url"]
            }
        )
    ]

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """列出可用的prompt模板"""
    logger.debug("Listing available prompts")
    return [
        types.Prompt(
            name="code-review",
            description="Review code changes in a GitHub pull request",
            arguments=[
                types.PromptArgument(
                    name="pr_url",
                    description="GitHub PR URL",
                    required=True
                ),
                types.PromptArgument(
                    name="focus",
                    description="Review focus area (e.g. security, performance, tests)",
                    required=False
                )
            ]
        ),
        types.Prompt(
            name="summarize-pr",
            description="Get a concise summary of PR changes",
            arguments=[
                types.PromptArgument(
                    name="pr_url",
                    description="GitHub PR URL",
                    required=True
                )
            ]
        )
    ]

def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """解析PR URL获取owner、repo和PR number"""
    logger.debug(f"Parsing PR URL: {pr_url}")
    try:
        parts = pr_url.split('/')
        owner = parts[-4]
        repo = parts[-3]
        pr_number = int(parts[-1])
        logger.debug(f"Parsed PR URL - owner: {owner}, repo: {repo}, PR number: {pr_number}")
        return owner, repo, pr_number
    except (IndexError, ValueError) as e:
        logger.error(f"Failed to parse PR URL: {pr_url}", exc_info=True)
        raise ValueError(f"Invalid PR URL format: {e}")

def get_pr_content(pr_url: str) -> dict[str, Any]:
    """获取PR内容，包括评论和review信息"""
    logger.info(f"Fetching PR content for URL: {pr_url}")
    try:
        owner, repo, pr_number = parse_pr_url(pr_url)
        repo = g.get_repo(f"{owner}/{repo}")
        logger.debug(f"Accessing repository: {owner}/{repo}")
        
        pr = repo.get_pull(pr_number)
        logger.debug(f"Retrieved PR #{pr_number}")
        
        # 获取PR评论
        logger.debug("Fetching PR comments...")
        comments = []
        for comment in pr.get_issue_comments():
            comments.append({
                'user': comment.user.login,
                'body': comment.body,
                'created_at': comment.created_at.isoformat(),
                'updated_at': comment.updated_at.isoformat()
            })
            logger.debug(f"Processed comment by {comment.user.login}")
        
        # 获取PR review评论
        logger.debug("Fetching PR review comments...")
        review_comments = []
        for comment in pr.get_review_comments():
            review_comments.append({
                'user': comment.user.login,
                'body': comment.body,
                'path': comment.path,
                'position': comment.position,
                'created_at': comment.created_at.isoformat(),
                'updated_at': comment.updated_at.isoformat()
            })
            logger.debug(f"Processed review comment by {comment.user.login} on {comment.path}")
        
        # 获取PR reviews
        logger.debug("Fetching PR reviews...")
        reviews = []
        for review in pr.get_reviews():
            reviews.append({
                'user': review.user.login,
                'state': review.state,
                'body': review.body,
                'submitted_at': review.submitted_at.isoformat() if review.submitted_at else None
            })
            logger.debug(f"Processed review by {review.user.login}: {review.state}")
        
        # 获取文件变更
        files = []
        logger.debug("Fetching PR files...")
        for file in pr.get_files():
            files.append({
                'filename': file.filename,
                'status': file.status,
                'changes': file.changes,
                'patch': file.patch
            })
            logger.debug(f"Processed file: {file.filename}")
        
        content = {
            'title': pr.title,
            'body': pr.body,
            'state': pr.state,
            'mergeable': pr.mergeable,
            'mergeable_state': pr.mergeable_state,
            'files': files,
            'additions': pr.additions,
            'deletions': pr.deletions,
            'changed_files': pr.changed_files,
            'comments': comments,
            'review_comments': review_comments,
            'reviews': reviews,
            'labels': [label.name for label in pr.labels],
            'created_at': pr.created_at.isoformat(),
            'updated_at': pr.updated_at.isoformat(),
            'author': pr.user.login
        }
        
        logger.info(f"Successfully retrieved PR content with {len(files)} files, "
                   f"{len(comments)} comments, {len(review_comments)} review comments, "
                   f"and {len(reviews)} reviews")
        return content
        
    except Exception as e:
        logger.error(f"Error fetching PR content: {e}", exc_info=True)
        raise

@server.call_tool()
async def handle_call_tool(
    name: str, 
    arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """处理工具调用"""
    logger.info(f"Tool call received: {name}")
    logger.debug(f"Tool arguments: {arguments}")
    
    if not arguments:
        logger.error("Missing arguments in tool call")
        raise ValueError("Missing arguments")
        
    if name == "review-pr":
        pr_url = arguments.get("pr_url")
        if not pr_url:
            logger.error("Missing PR URL in review-pr tool call")
            raise ValueError("Missing PR URL")
            
        try:
            pr_content = get_pr_content(pr_url)
            logger.debug("Formatting PR content for output")
            
            # 格式化输出
            output = [
                f"PR Title: {pr_content['title']}\n",
                f"Author: {pr_content['author']}",
                f"State: {pr_content['state']}",
                f"Created: {pr_content['created_at']}",
                f"Updated: {pr_content['updated_at']}\n",
                f"Description: {pr_content['body']}\n",
                f"Changes: +{pr_content['additions']} -{pr_content['deletions']} in {pr_content['changed_files']} files",
                f"Labels: {', '.join(pr_content['labels'])}\n",
                f"Mergeable: {pr_content['mergeable']} ({pr_content['mergeable_state']})\n",
                "\nReviews:\n"
            ]
            
            # 添加reviews信息
            for review in pr_content['reviews']:
                output.append(f"- {review['user']} ({review['state']})")
                if review['body']:
                    output.append(f"  Comment: {review['body']}")
            
            output.append("\nComments:\n")
            # 添加常规评论
            for comment in pr_content['comments']:
                output.append(f"- {comment['user']} at {comment['created_at']}:")
                output.append(f"  {comment['body']}")
            
            output.append("\nReview Comments:\n")
            # 添加代码行评论
            for comment in pr_content['review_comments']:
                output.append(f"- {comment['user']} on {comment['path']} at position {comment['position']}:")
                output.append(f"  {comment['body']}")
            
            output.append("\nModified files:\n")
            # 添加文件变更信息
            for file in pr_content['files']:
                output.append(f"\nFile: {file['filename']}")
                output.append(f"Status: {file['status']}")
                output.append(f"Changes: {file['changes']} lines")
                if file['patch']:
                    output.append("Diff:")
                    output.append(file['patch'])
            
            logger.info("Successfully generated PR review output")
            return [types.TextContent(
                type="text",
                text="\n".join(output)
            )]
            
        except Exception as e:
            logger.error(f"Error in review-pr tool: {e}", exc_info=True)
            return [types.TextContent(
                type="text", 
                text=f"Error retrieving PR content: {str(e)}"
            )]
            
    logger.error(f"Unknown tool called: {name}")
    raise ValueError(f"Unknown tool: {name}")

@server.get_prompt()
async def handle_get_prompt(
    name: str,
    arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """处理prompt请求"""
    logger.info(f"Prompt request received: {name}")
    logger.debug(f"Prompt arguments: {arguments}")
    
    if not arguments or "pr_url" not in arguments:
        logger.error("Missing PR URL in prompt arguments")
        raise ValueError("Missing PR URL argument")
        
    try:
        pr_content = get_pr_content(arguments["pr_url"])
        
        if name == "code-review":
            focus = arguments.get("focus", "general")
            prompt_text = f"""Please review this pull request{f' focusing on {focus}' if focus != 'general' else ''}:

Title: {pr_content['title']}
Author: {pr_content['author']}
Description:
{pr_content['body']}

Changes: +{pr_content['additions']} -{pr_content['deletions']} in {pr_content['changed_files']} files

Previous reviews and comments:
{format_review_history(pr_content)}

Please provide a thorough code review that includes:
1. Code quality and style analysis
2. Potential bugs or issues
3. {'Security implications and vulnerabilities' if focus == 'security' else 'Performance implications' if focus == 'performance' else 'General implementation concerns'}
4. Test coverage assessment
5. Documentation completeness
6. Specific recommendations for improvement

For each modified file, please analyze:
- The purpose and impact of changes
- Code structure and organization
- Potential edge cases
- {'Security risks and mitigations' if focus == 'security' else 'Performance bottlenecks' if focus == 'performance' else 'Areas for improvement'}

Please be thorough but constructive in your feedback.
"""
            return types.GetPromptResult(
                description=f"Code review for PR{f' focusing on {focus}' if focus != 'general' else ''}",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=prompt_text
                        )
                    )
                ]
            )
            
        elif name == "summarize-pr":
            prompt_text = f"""Please provide a concise summary of this pull request:

Title: {pr_content['title']}
Author: {pr_content['author']}

Key Information:
- Changes: +{pr_content['additions']} -{pr_content['deletions']} in {pr_content['changed_files']} files
- Status: {pr_content['state']}
- Labels: {', '.join(pr_content['labels'])}

Description:
{pr_content['body']}

Modified Files Overview:
{format_file_summary(pr_content['files'])}

Please provide:
1. A brief overview of the main changes
2. The purpose and impact of these changes
3. Current review status and any concerns raised
4. Next steps or pending actions

Keep the summary clear and focused on the most important aspects.
"""
            return types.GetPromptResult(
                description="PR summary",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=prompt_text
                        )
                    )
                ]
            )
            
        logger.error(f"Unknown prompt requested: {name}")
        raise ValueError(f"Unknown prompt: {name}")
        
    except Exception as e:
        logger.error(f"Error generating prompt: {e}", exc_info=True)
        raise ValueError(f"Error generating prompt: {str(e)}")

def format_review_history(pr_content: dict) -> str:
    """格式化review历史"""
    history = []
    
    # 添加reviews
    if pr_content['reviews']:
        history.append("Reviews:")
        for review in pr_content['reviews']:
            history.append(f"- {review['user']} ({review['state']})")
            if review['body']:
                history.append(f"  Comment: {review['body']}")
    
    # 添加评论
    if pr_content['comments']:
        history.append("\nGeneral Comments:")
        for comment in pr_content['comments']:
            history.append(f"- {comment['user']}: {comment['body']}")
    
    # 添加review comments
    if pr_content['review_comments']:
        history.append("\nCode Comments:")
        for comment in pr_content['review_comments']:
            history.append(f"- {comment['user']} on {comment['path']}: {comment['body']}")
    
    return "\n".join(history)

def format_file_summary(files: list) -> str:
    """格式化文件变更摘要"""
    summary = []
    for file in files:
        summary.append(f"- {file['filename']}")
        summary.append(f"  Changes: {file['changes']} lines ({file['status']})")
    return "\n".join(summary)

async def main():
    """运行服务器"""
    logger.info("Starting MCP server...")
    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            logger.debug("STDIO transport initialized")
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="github-review",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                    )
                )
            )
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise
    finally:
        logger.info("Server shutdown")

if __name__ == "__main__":
    asyncio.run(main()) 