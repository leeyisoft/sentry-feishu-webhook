#!/usr/bin/env python3
"""
测试脚本：模拟 Sentry 实际发送的 webhook 数据格式
"""
import json
import httpx

# 基于实际日志的 Sentry webhook 数据格式
sentry_webhook_data = {
    "id": "18",
    "project": "midooserver-dev",
    "project_name": "midooserver-dev",
    "project_slug": "midooserver-dev",
    "logger": None,
    "level": "error",
    "culprit": "../../sentry/scripts/views.js in poll",
    "message": "This is an example Go exception",
    "url": "http://47.236.137.231:9000/organizations/sentry/issues/18/?referrer=webhooks_plugin",
    "triggering_rules": [""],
    "event": {
        "event_id": "612e5ffe74b9421f8e0f74da884ed301",
        "level": "error",
        "version": "5",
        "tags": [
            {"key": "environment", "value": "production"}
        ]
    }
}

def test_webhook():
    try:
        response = httpx.post(
            "http://localhost:8000/webhook/sentry",
            json=sentry_webhook_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("\n✅ 测试成功！请检查飞书群是否收到消息。")
        else:
            print(f"\n❌ 测试失败: {response.text}")
            
    except httpx.ConnectError:
        print("❌ 无法连接到服务，请确保服务正在运行")
        print("运行命令: python main.py")
    except Exception as e:
        print(f"❌ 错误: {str(e)}")

if __name__ == "__main__":
    print("🚀 测试 Sentry Webhook（使用实际数据格式）...\n")
    test_webhook()