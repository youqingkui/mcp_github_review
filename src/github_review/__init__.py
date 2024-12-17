import logging
from . import server

# 配置日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
        logging.FileHandler('github_review.log')  # 输出到文件
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main entry point for the package."""
    import asyncio
    logger.info("Starting GitHub Review MCP server...")
    try:
        asyncio.run(server.main())
    except Exception as e:
        logger.error(f"Error running server: {e}", exc_info=True)
        raise

__all__ = ['main', 'server'] 