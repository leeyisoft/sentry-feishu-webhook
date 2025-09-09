#!/usr/bin/env python3
import json
import httpx
import sys

def test_sentry_webhook():
    """测试 Sentry webhook 端点"""
    
    # 模拟 Sentry 发送的 webhook 数据
    sentry_payload = {
        "action": "created",
        "data": {
            "issue": {
                "title": "TypeError: Cannot read property 'user' of undefined",
                "url": "https://sentry.example.com/organizations/my-org/issues/12345/",
                "project": {
                    "name": "Production API"
                },
                "tags": {
                    "environment": "production"
                },
                "level": "error",
                "culprit": "api/handlers/user.js in getUserInfo",
                "message": "TypeError: Cannot read property 'user' of undefined\n  at getUserInfo (api/handlers/user.js:45:12)\n  at async handleRequest (api/middleware/auth.js:23:5)"
            }
        }
    }
    
    try:
        # 发送请求到本地服务
        response = httpx.post(
            "http://localhost:8000/webhook/sentry",
            json=sentry_payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("\n✅ Webhook 测试成功！")
            print("请检查飞书群是否收到通知消息。")
        else:
            print("\n❌ Webhook 测试失败")
            
    except httpx.ConnectError:
        print("❌ 无法连接到服务，请确保服务正在运行")
        print("运行命令: python notify/main.py")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        sys.exit(1)

def test_feishu_notification():
    """测试飞书通知端点"""
    try:
        response = httpx.post("http://localhost:8000/test/feishu")
        print(f"\n飞书测试端点状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("\n✅ 飞书测试通知发送成功！")
        else:
            print("\n❌ 飞书测试通知发送失败")
            
    except Exception as e:
        print(f"❌ 飞书测试失败: {str(e)}")

if __name__ == "__main__":
    print("🚀 开始测试 Sentry-Feishu Webhook 服务...\n")
    
    # 测试健康检查
    try:
        response = httpx.get("http://localhost:8000/health")
        if response.status_code == 200:
            print("✅ 服务健康检查通过\n")
        else:
            print("❌ 服务健康检查失败")
            sys.exit(1)
    except:
        print("❌ 服务未运行，请先启动服务")
        print("运行命令: python notify/main.py")
        sys.exit(1)
    
    # 测试 Sentry webhook
    print("1️⃣ 测试 Sentry Webhook 处理...")
    test_sentry_webhook()
    
    # 测试飞书通知
    print("\n2️⃣ 测试飞书通知发送...")
    test_feishu_notification()
    
    print("\n✨ 所有测试完成！")