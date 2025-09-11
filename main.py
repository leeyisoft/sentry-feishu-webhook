import os
import json
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

app = FastAPI(title="Sentry to Feishu Webhook Service", version="1.0.0")

FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")
# 临时开启调试模式
DEBUG_MODE = os.getenv("DEBUG_MODE", "true").lower() == "true"

# 解析忽略的项目ID配置
def parse_ignore_project_ids() -> List[Any]:
    """解析忽略的项目ID配置，支持数字和字符串"""
    ignore_config = os.getenv("IGNORE_TO_FEECHU_PROJECT_IDS", "[]")
    try:
        # 移除可能的空格并解析JSON
        ignore_config = ignore_config.strip()
        if ignore_config.startswith('[') and ignore_config.endswith(']'):
            return json.loads(ignore_config)
        else:
            # 如果不是JSON格式，尝试按逗号分割
            items = [item.strip().strip('"').strip("'") for item in ignore_config.split(',')]
            result = []
            for item in items:
                if item.isdigit():
                    result.append(int(item))
                else:
                    result.append(item)
            return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse IGNORE_TO_FEECHU_PROJECT_IDS: {e}, using empty list")
        return []

IGNORE_PROJECT_IDS = parse_ignore_project_ids()


def should_ignore_project(issue_data: Dict[str, Any]) -> bool:
    """检查项目是否应该被忽略"""
    if not IGNORE_PROJECT_IDS:
        return False
    
    # 提取项目信息
    project = FeishuMessage._extract_nested_value(issue_data, 'project')
    
    if project is None:
        return False
    
    # 如果project是字典，提取ID和名称
    if isinstance(project, dict):
        project_id = project.get('id')
        project_name = project.get('name', project.get('slug', ''))
        
        # 检查项目ID或名称是否在忽略列表中
        for ignore_item in IGNORE_PROJECT_IDS:
            if project_id == ignore_item or project_name == ignore_item:
                return True
    
    # 如果project是数字或字符串，直接比较
    elif isinstance(project, (int, str)):
        for ignore_item in IGNORE_PROJECT_IDS:
            if project == ignore_item:
                return True
    
    return False


if DEBUG_MODE:
    logger.add("debug.log", rotation="10 MB", level="DEBUG")
else:
    logger.add("app.log", rotation="10 MB", level="INFO")


class FeishuMessage:
    @staticmethod
    def _extract_nested_value(data: Dict[str, Any], *paths: str) -> Any:
        """从嵌套字典中提取值，支持多个可能的路径"""
        for path in paths:
            keys = path.split('.')
            value = data
            try:
                for key in keys:
                    # 处理数组索引，如 frames.0 或 frames.-1
                    if key.isdigit() and isinstance(value, list):
                        index = int(key)
                        if 0 <= index < len(value):
                            value = value[index]
                        else:
                            value = None
                            break
                    elif key.startswith('-') and key[1:].isdigit() and isinstance(value, list):
                        index = int(key)
                        if abs(index) <= len(value):
                            value = value[index]
                        else:
                            value = None
                            break
                    elif isinstance(value, dict) and key in value:
                        value = value[key]
                    elif isinstance(value, list) and len(value) > 0:
                        # 如果是列表，尝试获取第一个元素
                        value = value[0]
                        if isinstance(value, dict) and key in value:
                            value = value[key]
                        else:
                            value = None
                            break
                    else:
                        value = None
                        break
                if value is not None:
                    return value
            except (TypeError, AttributeError, IndexError):
                continue
        return None

    @staticmethod
    def _extract_culprit_with_line(issue_data: Dict[str, Any]) -> str:
        """提取包含文件名和行号的位置信息"""
        # 1. 提取基础信息
        culprit = FeishuMessage._extract_nested_value(issue_data, 'culprit')
        location = FeishuMessage._extract_nested_value(issue_data, 'location')

        # 2. 尝试从异常堆栈中提取行号信息
        line_no = None
        frames = None

        try:
            # 获取异常堆栈帧 - 支持多种可能的路径
            frames = FeishuMessage._extract_nested_value(
                issue_data,
                'exception.values.0.stacktrace.frames',
                'stacktrace.frames',
                'entries.0.data.values.0.stacktrace.frames',
                'data.error.exception.values.0.stacktrace.frames'
            )

            if frames and isinstance(frames, list):
                # 查找 in_app 为 true 的帧（应用代码）
                target_frame = None
                for frame in reversed(frames):
                    if isinstance(frame, dict) and frame.get('in_app', False):
                        target_frame = frame
                        break

                # 如果没有找到 in_app 的帧，使用最后一个帧
                if target_frame is None and frames:
                    target_frame = frames[-1]

                if target_frame and isinstance(target_frame, dict):
                    line_no = target_frame.get('lineno')
        except (TypeError, AttributeError, IndexError, ValueError) as e:
            logger.debug(f"Error extracting line number: {e}")
            pass

        # 3. 如果有 location 信息，优先整合 location
        if location and location != "Unknown":
            # 如果 location 已经包含行号信息，直接返回
            if line_no and str(line_no) in location:
                return location

            # 如果 location 是有效的文件路径，添加行号信息
            if location and any(char in location for char in ['/', '\\', '.']):
                if line_no:
                    return f"{location} at line {line_no}"
                else:
                    return location

            # 如果 location 不是文件路径，但与 culprit 不同，可以组合显示
            if culprit and culprit != location:
                if line_no:
                    return f"{culprit} ({location}) at line {line_no}"
                else:
                    return f"{culprit} ({location})"

        # 4. 尝试从堆栈帧中构建完整的位置信息
        try:
            if frames and isinstance(frames, list):
                target_frame = None
                for frame in reversed(frames):
                    if isinstance(frame, dict) and frame.get('in_app', False):
                        target_frame = frame
                        break

                if target_frame is None and frames:
                    target_frame = frames[-1]

                if target_frame and isinstance(target_frame, dict):
                    filename = target_frame.get('filename', 'Unknown file')
                    line_no = target_frame.get('lineno')
                    function = target_frame.get('function', 'Unknown function')

                    if filename and filename != "Unknown file":
                        if line_no:
                            return f"{filename} in {function} at line {line_no}"
                        else:
                            return f"{filename} in {function}"
        except (TypeError, AttributeError, IndexError):
            pass

        # 5. 尝试从 metadata 中提取
        filename = FeishuMessage._extract_nested_value(
            issue_data,
            'metadata.filename',
            'metadata.abs_path'
        )

        if filename:
            line_no_meta = FeishuMessage._extract_nested_value(
                issue_data,
                'metadata.lineno',
                'metadata.line'
            ) or line_no  # 使用之前提取的行号作为备选

            function = FeishuMessage._extract_nested_value(
                issue_data,
                'metadata.function',
                'metadata.module'
            ) or 'Unknown function'

            if filename and line_no_meta:
                return f"{filename} in {function} at line {line_no_meta}"
            elif filename:
                return f"{filename} in {function}"

        # 6. 如果有 culprit 信息
        if culprit and culprit != "Unknown" and culprit != "root /":
            if line_no:
                # 检查 culprit 是否已经包含行号
                has_line_info = any([
                    f"line {line_no}" in culprit,
                    f":{line_no}" in culprit,
                    f" at {line_no}" in culprit,
                    f"#{line_no}" in culprit
                ])

                if not has_line_info:
                    return f"{culprit} at line {line_no}"
            return culprit

        # 7. 最后回退到 location 或默认值
        if location and location != "Unknown":
            if line_no:
                return f"{location} at line {line_no}"
            return location

        # 8. 最终回退
        if line_no:
            return f"Unknown location at line {line_no}"

        return "Unknown location"

    @staticmethod
    def _extract_environment(issue_data: Dict[str, Any]) -> str:
        """从多个可能的位置提取环境信息"""
        # 1. 直接从环境字段获取
        environment = FeishuMessage._extract_nested_value(issue_data, 'environment')
        if environment and environment != "Unknown":
            return environment

        # 2. 从 tags 中提取
        tags = FeishuMessage._extract_nested_value(issue_data, 'tags')
        if tags:
            if isinstance(tags, dict):
                environment = tags.get('environment', 'Unknown')
            elif isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, dict):
                        if tag.get('key') == 'environment':
                            return tag.get('value', 'Unknown')
                        elif 'environment' in tag:
                            return tag.get('environment', 'Unknown')
                    elif isinstance(tag, list) and len(tag) == 2 and tag[0] == 'environment':
                        return tag[1]

        # 3. 从 _dsc 中提取
        environment = FeishuMessage._extract_nested_value(issue_data, '_dsc.environment')
        if environment and environment != "Unknown":
            return environment

        return "Unknown"

    @staticmethod
    def _extract_project_name(issue_data: Dict[str, Any]) -> str:
        """提取项目名称"""
        # 从错误数据中提取项目信息
        project = FeishuMessage._extract_nested_value(issue_data, 'project')
        if isinstance(project, dict):
            return project.get('name', project.get('slug', 'Unknown Project'))
        elif isinstance(project, str):
            return project
        elif isinstance(project, int):
            # 如果是数字ID，可以尝试映射或返回默认值
            return f"Project-{project}"
        else:
            return "Unknown Project"

    @staticmethod
    def build_message(issue_data: Dict[str, Any]) -> Dict[str, Any]:
        # 调试：记录完整的数据结构
        logger.debug(f"Raw issue data keys: {list(issue_data.keys())}")

        # 从 Sentry webhook 数据中提取信息
        # 标题可以从多个位置获取
        title = FeishuMessage._extract_nested_value(
            issue_data,
            'title',
            'metadata.value',
            'metadata.type',
            'exception.values.0.type',
            'exception.values.0.value'
        ) or "Unknown Issue"

        # URL 可以从多个位置获取
        url = FeishuMessage._extract_nested_value(
            issue_data,
            'web_url',
            'issue_url',
            'url'
        ) or ""

        # 提取项目名称
        project_name = FeishuMessage._extract_project_name(issue_data)

        # 提取环境信息
        environment = FeishuMessage._extract_environment(issue_data)

        # 提取级别
        level = FeishuMessage._extract_nested_value(
            issue_data,
            'level',
            'metadata.level',
            'tags.level'
        ) or "error"

        # 提取包含行号的位置信息
        culprit = FeishuMessage._extract_culprit_with_line(issue_data)

        # 提取消息详情
        message = FeishuMessage._extract_nested_value(
            issue_data,
            'message',
            'metadata.value',
            'exception.values.0.value',
            'title'
        ) or "No message provided"

        # 如果消息太长，截断
        if isinstance(message, str) and len(message) > 300:
            message = message[:297] + "..."

        level_emoji = {
            "fatal": "🔴",
            "error": "🟠",
            "warning": "🟡",
            "info": "🔵",
            "debug": "⚪"
        }.get(level.lower(), "⚫")

        # 构建消息内容
        msg_content = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "content": f"{level_emoji} Sentry Issue Alert",
                        "tag": "plain_text"
                    },
                    "template": "red" if level.lower() in ["fatal", "error"] else "orange" if level.lower() == "warning" else "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "content": f"**项目**: {project_name}\n**环境**: {environment}\n**级别**: {level.upper()}",
                            "tag": "lark_md"
                        }
                    },
                    {
                        "tag": "div",
                        "text": {
                            "content": f"**标题**: {title}\n**位置**: {culprit}",
                            "tag": "lark_md"
                        }
                    },
                    {
                        "tag": "hr"
                    }
                    # 注释@所有人
                    # , {
                    #     "tag": "div",
                    #     "text": {
                    #         "content": "<at id=all></at> 请相关同学及时处理",
                    #         "tag": "lark_md"
                    #     }
                    # }
                ]
            }
        }

        # 只有在 message 不为空时才添加详情部分
        if message and message != "" and message != "No message provided":
            msg_content["card"]["elements"].append({
                "tag": "div",
                "text": {
                    "content": f"**详情**: {message}",
                    "tag": "lark_md"
                }
            })

        # 只有在有有效 URL 时才添加查看详情按钮
        if url and url.startswith(('http://', 'https://')):
            msg_content["card"]["elements"].extend([
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "查看详情"
                            },
                            "type": "primary",
                            "url": url
                        }
                    ]
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                }
            ])
        else:
            msg_content["card"]["elements"].append({
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                ]
            })

        return msg_content


class WebhookHandler:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            proxies=None
        )

    async def send_to_feishu(self, issue_data: Dict[str, Any]) -> bool:
        try:
            if not FEISHU_WEBHOOK_URL or not FEISHU_WEBHOOK_URL.startswith(('http://', 'https://')):
                logger.error(f"Invalid FEISHU_WEBHOOK_URL: '{FEISHU_WEBHOOK_URL}'")
                return False

            try:
                message = FeishuMessage.build_message(issue_data)
                if DEBUG_MODE:
                    logger.debug(f"Built message: {json.dumps(message, indent=2, ensure_ascii=False)}")
            except Exception as e:
                logger.error(f"Failed to build message: {str(e)}")
                logger.error(f"Issue data keys: {list(issue_data.keys())}")
                return False

            response = await self.client.post(
                FEISHU_WEBHOOK_URL,
                json=message,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    logger.info("Successfully sent message to Feishu")
                    return True
                else:
                    logger.error(f"Feishu API error: {result}")
                    return False
            else:
                logger.error(f"HTTP error: {response.status_code}, response: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send to Feishu: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False


webhook_handler = WebhookHandler()


@app.on_event("startup")
async def startup_event():
    logger.info("Sentry-Feishu webhook service started")
    if not FEISHU_WEBHOOK_URL:
        logger.warning("FEISHU_WEBHOOK_URL not configured")
    
    if IGNORE_PROJECT_IDS:
        logger.info(f"Configured to ignore projects: {IGNORE_PROJECT_IDS}")
    else:
        logger.info("No projects configured to be ignored")


@app.on_event("shutdown")
async def shutdown_event():
    await webhook_handler.client.aclose()
    logger.info("Sentry-Feishu webhook service stopped")


@app.get("/")
async def root():
    return {
        "service": "Sentry to Feishu Webhook",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/webhook/sentry")
async def receive_sentry_webhook(request: Request):
    try:
        body = await request.body()
        if DEBUG_MODE:
            logger.debug(f"receive_sentry_webhook body: {body}")
        data = json.loads(body)

        logger.info(f"Received webhook with keys: {list(data.keys())}")

        if DEBUG_MODE:
            logger.debug(f"Webhook action: {data.get('action')}")

        action = data.get("action", "unknown")
        # 检查项目是否应该被忽略
        if should_ignore_project(data):
            project = FeishuMessage._extract_nested_value(data, 'project')
            project_info = ""
            if isinstance(project, dict):
                project_info = f"ID: {project.get('id')}, Name: {project.get('name', project.get('slug', 'Unknown'))}"
            else:
                project_info = str(project)
            
            logger.info(f"Ignoring project in ignore list: {project_info}")
            return {
                "status": "ignored", 
                "message": f"Project {project_info} is in ignore list",
                "action": action
            }

        issue_data = None
        if "data" in data:
            # 处理 Sentry webhook 格式 - 数据可能在 data.error 中
            if "error" in data["data"]:
                issue_data = data["data"]["error"]  # 错误数据在 data.error 中
                # logger.info("Found error data in data.error")
            else:
                issue_data = data["data"]  # 或者直接在 data 中
                logger.info("Found data directly in data")

            # logger.info(f"Processing {action} action for issue")

            if action != "created":
                logger.info(f"Ignoring non-created action: {action}")
                return {"status": "ignored", "message": f"Action {action} ignored"}

        elif "id" in data and ("message" in data or "title" in data):
            issue_data = data
            action = "direct"
            logger.info("Processing direct issue data")
        else:
            logger.error(f"Invalid webhook data. Keys: {list(data.keys())}")
            raise HTTPException(status_code=400, detail="Invalid webhook data format")


        success = await webhook_handler.send_to_feishu(issue_data)

        if success:
            return {
                "status": "success",
                "message": "Notification sent to Feishu",
                "action": action
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send to Feishu")

    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test/feishu")
async def test_feishu_notification():
    test_issue = {
        "title": "Test Issue: This is a test notification",
        "url": "https://sentry.io/test",
        "project": {"name": "Test Project"},
        "tags": {"environment": "test"},
        "level": "error",
        "culprit": "test.module.function",
        "message": "This is a test message to verify Feishu integration is working correctly."
    }
    
    success = await webhook_handler.send_to_feishu(test_issue)
    
    if success:
        return {"status": "success", "message": "Test notification sent"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test notification")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
