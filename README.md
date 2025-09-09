# Sentry to Feishu Webhook 中台服务

一个用于接收自建部署 Sentry 的 issue webhook 并发送通知到飞书群的中台服务。

## 功能特性

- ✅ 接收 Sentry webhook 事件
- ✅ 发送富文本卡片消息到飞书群
- ✅ 支持 @所有人 提醒
- ✅ 显示 issue 标题（可点击跳转到 Sentry）
- ✅ 支持 Sentry 签名验证
- ✅ 支持飞书签名验证
- ✅ Docker 容器化部署
- ✅ 详细的日志记录

## 快速开始

### 1. 配置飞书机器人

1. 在飞书群中添加自定义机器人
2. 获取 Webhook URL
3. （可选）配置签名验证并获取签名密钥

### 2. 配置 Sentry Webhook

在 Sentry 项目中配置 Webhook：

1. 进入项目设置 -> Integrations -> Webhooks
2. 添加 Webhook URL: `http://your-server:8000/webhook/sentry`

http://172.26.86.198:8000/webhook/sentry
3. 选择要监听的事件（建议选择 issue.created, issue.resolved, issue.assigned）

### 3. 部署服务

#### 方式一：使用 Docker Compose（推荐）

```bash
# 1. 克隆或创建项目目录
cd notify

# 2. 复制环境变量配置文件
cp .env.example .env

# 3. 编辑 .env 文件，填入实际的配置
vim .env

# 4. 启动服务
docker-compose up -d

# 5. 查看日志
docker-compose logs -f
```

#### 方式二：直接运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
vim .env

# 3. 运行服务
python main.py
```

#### 方式三：使用 systemd（生产环境）

创建 systemd 服务文件 `/etc/systemd/system/sentry-feishu.service`:

```ini
[Unit]
Description=Sentry to Feishu Webhook Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/notify
Environment="PATH=/opt/notify/venv/bin"
ExecStart=/opt/notify/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable sentry-feishu
sudo systemctl start sentry-feishu
sudo systemctl status sentry-feishu
```

## 环境变量配置

| 变量名 | 描述 | 必填 | 示例 |
|--------|------|------|------|
| FEISHU_WEBHOOK_URL | 飞书机器人 Webhook URL | ✅ | https://open.feishu.cn/open-apis/bot/v2/hook/xxx |
| PORT | 服务监听端口 | ❌ | 8000 |
| DEBUG_MODE | 调试模式 | ❌ | false |

## API 端点

### 健康检查

```bash
GET /health
```

### 接收 Sentry Webhook

```bash
POST /webhook/sentry
```

### 测试飞书通知

```bash
POST /test/feishu
```

发送测试通知到飞书群，用于验证配置是否正确。

## 飞书消息格式

消息会以卡片形式发送，包含以下信息：

- 🔴/🟠/🟡/🔵 不同级别的 Issue 标识
- 项目名称和环境
- Issue 标题（可点击跳转）
- 错误位置和详情
- @所有人 提醒
- 查看详情按钮
- 时间戳

## 故障排查

### 1. 飞书收不到消息

- 检查 FEISHU_WEBHOOK_URL 是否正确
- 检查飞书机器人是否启用
- 如果配置了签名，检查 FEISHU_SECRET 是否正确
- 查看服务日志：`docker-compose logs` 或查看 `app.log`

### 2. 测试功能

使用测试端点验证飞书集成：

```bash
curl -X POST http://localhost:8000/test/feishu
```

## 安全建议

1. **内网部署**: 建议部署在内网环境，通过内网访问
2. **配置飞书签名**: 如需增强安全，可在飞书机器人中开启签名验证
3. **限制访问**: 使用防火墙或安全组限制只允许 Sentry 服务器访问
4. **定期更新**: 保持依赖包更新到最新版本

## 性能优化

- 服务使用异步处理，支持高并发
- 配置了连接池和超时设置
- 日志文件自动轮转（10MB）

## 监控建议

1. 配置进程监控（如 supervisord 或 systemd）
2. 设置日志告警
3. 监控服务端口可用性
4. 定期检查日志文件大小

## License

MIT
