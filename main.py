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
DEBUG_MODE = os.getenv("DEBUG_MODE", "true").lower() == "true"  # 临时开启调试模式

if DEBUG_MODE:
    logger.add("debug.log", rotation="10 MB", level="DEBUG")
else:
    logger.add("app.log", rotation="10 MB", level="INFO")


class FeishuMessage:
    @staticmethod
    def build_message(issue_data: Dict[str, Any]) -> Dict[str, Any]:
        # 从 Sentry webhook 数据中提取信息
        title = issue_data.get("title") or issue_data.get("message", "Unknown Issue")
        url = issue_data.get("url", "")
        
        # project 可能是字符串或对象
        project = issue_data.get("project")
        if isinstance(project, dict):
            project_name = project.get("name", "Unknown Project")
        elif isinstance(project, str):
            project_name = project
        else:
            project_name = issue_data.get("project_name", "Unknown Project")
        
        # 尝试从多个位置获取环境信息
        environment = "Unknown"
        
        # 处理 tags 字段 - 可能是字典或列表
        if "tags" in issue_data:
            tags = issue_data["tags"]
            if isinstance(tags, dict):
                environment = tags.get("environment", "Unknown")
            elif isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, dict) and tag.get("key") == "environment":
                        environment = tag.get("value", "Unknown")
                        break
        
        # 如果还没找到，尝试从 event.tags 中获取
        if environment == "Unknown" and "event" in issue_data:
            event = issue_data["event"]
            if isinstance(event, dict) and "tags" in event:
                event_tags = event["tags"]
                if isinstance(event_tags, list):
                    for tag in event_tags:
                        if isinstance(tag, dict) and tag.get("key") == "environment":
                            environment = tag.get("value", "Unknown")
                            break
                elif isinstance(event_tags, dict):
                    environment = event_tags.get("environment", "Unknown")
        
        level = issue_data.get("level", "error")
        culprit = issue_data.get("culprit", "Unknown")
        message = issue_data.get("message", "No message provided")
        
        level_emoji = {
            "fatal": "🔴",
            "error": "🟠",
            "warning": "🟡",
            "info": "🔵",
            "debug": "⚪"
        }.get(level, "⚫")
        
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
                    "template": "red" if level in ["fatal", "error"] else "orange" if level == "warning" else "blue"
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
                            "content": f"**标题**: [{title}]({url})\n**位置**: {culprit}",
                            "tag": "lark_md"
                        }
                    },
                    {
                        "tag": "div",
                        "text": {
                            "content": f"**详情**: {message[:200]}{'...' if len(message) > 200 else ''}",
                            "tag": "lark_md"
                        }
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "tag": "div",
                        "text": {
                            "content": "<at id=all></at> 请相关同学及时处理",
                            "tag": "lark_md"
                        }
                    },
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
                ]
            }
        }
        
        return msg_content


class WebhookHandler:
    def __init__(self):
        # 禁用代理，避免SOCKS代理问题
        self.client = httpx.AsyncClient(
            timeout=30.0,
            proxies=None  # 显式禁用代理
        )
    
    async def send_to_feishu(self, issue_data: Dict[str, Any]) -> bool:
        try:
            # 检查飞书 Webhook URL 是否配置
            if not FEISHU_WEBHOOK_URL or not FEISHU_WEBHOOK_URL.startswith(('http://', 'https://')):
                logger.error(f"Invalid FEISHU_WEBHOOK_URL: '{FEISHU_WEBHOOK_URL}'")
                logger.error("Please set FEISHU_WEBHOOK_URL environment variable with your Feishu webhook URL")
                logger.error("Example: export FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx'")
                return False
            
            # 先构建消息，捕获可能的错误
            try:
                message = FeishuMessage.build_message(issue_data)
            except Exception as e:
                logger.error(f"Failed to build message: {str(e)}")
                logger.error(f"Issue data: {json.dumps(issue_data, indent=2)[:1000]}")
                return False
            
            logger.info(f"Sending to Feishu webhook: {FEISHU_WEBHOOK_URL[:50]}...")
            response = await self.client.post(
                FEISHU_WEBHOOK_URL,
                json=message,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    logger.info(f"Successfully sent message to Feishu")
                    return True
                else:
                    logger.error(f"Feishu API error: {result}")
                    return False
            else:
                logger.error(f"HTTP error: {response.status_code}")
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
        
        
        data = json.loads(body)
        
        # 记录接收到的完整数据结构
        logger.info(f"Received webhook data structure: {json.dumps(data, indent=2)[:500]}...")
        
        # Sentry webhook 直接发送 issue 数据
        # 判断是否为有效的 issue 数据
        if "id" in data and ("message" in data or "title" in data):
            # 这是一个有效的 issue 数据
            issue_data = data
            logger.info(f"Processing issue: {issue_data.get('id')} - {issue_data.get('message', '')}")
        else:
            logger.error(f"Invalid webhook data. Keys: {list(data.keys())}")
            raise HTTPException(status_code=400, detail="Invalid webhook data format")
        
        success = await webhook_handler.send_to_feishu(issue_data)
        
        if success:
            return {
                "status": "success",
                "message": "Notification sent to Feishu"
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