# Sentry to Feishu Webhook 中台服务
**sentry-feishu-webhook** 是一个专为开发团队打造的轻量级集成服务 ，专注于将 Sentry 错误监控系统的 Webhook 事件 实时、精准地推送到飞书。让团队第一时间感知生产环境异常，快速响应，守护代码质量；

该项目已开源至  [Gitee](https://gitee.com/leeyi/sentry-feishu-webhook) 和 [Github](https://github.com/leeyisoft/sentry-feishu-webhook)，支持多项目、多群组的灵活配置；

基于 MIT 开源协议 ，欢迎 Star ⭐、Fork 🍴 和贡献代码 💻。


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

### 1. 获取 Webhook URL

#### 方式一：飞书群机器人

1. 创建一个飞书群
2. 在群聊右上角点击设置按钮
3. 选择「群机器人」-> 「添加机器人」-> 「自定义机器人」
4. 填写机器人名称和描述
5. 复制生成的 Webhook URL
6. （可选）开启签名验证并记录签名密钥

#### 方式二：飞书开放平台

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 在「机器人」功能中获取 Webhook URL
4. 配置相应的权限和回调地址

#### 配置到项目中

将获取到的 Webhook URL 配置到项目的 `PROJECT_FEISHU_WEBHOOK_MAPPING` 环境变量中

### 2. 配置 Sentry Webhook

在 Sentry 管理后台中 项目中配置 Webhook：

1. 进入项目设置 -> Integrations -> Webhooks
2. 添加 Webhook URL: `http://your-server:8000/webhook/sentry`

http://172.26.86.198:8000/webhook/sentry
3. 选择要监听的事件（建议选择 issue.created, issue.resolved, issue.assigned）

### 3. 部署服务

#### 方式1：使用 systemd（生产环境）

创建 systemd 服务文件 `/etc/systemd/system/sentry-feishu.service`:

```ini
[Unit]
Description=Sentry to Feishu Webhook Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/usr/local/sentry-feishu-webhook
EnvironmentFile=/usr/local/sentry-feishu-webhook/.env
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10
StandardOutput=append:/usr/local/sentry-feishu-webhook/app.log
StandardError=append:/usr/local/sentry-feishu-webhook/app.log

[Install]
WantedBy=multi-user.target
```

```
# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 重启服务
sudo systemctl restart sentry-feishu

# 查看服务状态
sudo systemctl status sentry-feishu

# 查看实时日志
sudo journalctl -u sentry-feishu -f
```

vent

```ini
[Unit]
Description=Sentry to Feishu Webhook Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/usr/local/sentry-feishu-webhook
Environment="PATH=/usr/local/sentry-feishu-webhook/venv/bin"
ExecStart=/usr/local/sentry-feishu-webhook/venv/bin/python main.py
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


#### 方式2：使用 Docker Compose

```bash
# 1. 克隆或创建项目目录
cd notify

# 2. 复制环境变量配置文件
cp .env.example .env

# 3. 编辑 .env 文件，填入实际的配置
vim .env

# 4. 启动服务
docker compose up -d

# 针对 sentry-feishu-webhook 服务 加载新 env
docker compose up -d --force-recreate --wait sentry-feishu-webhook

# 5. 查看日志
docker compose logs -f
```

#### 方式3：直接运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
vim .env

# 3. 运行服务
python main.py
```

## 环境变量配置

### 基础配置

| 变量名 | 描述 | 必填 | 示例 |
|--------|------|------|------|
| FEISHU_WEBHOOK_URL | 默认飞书机器人 Webhook URL | ❌ | https://open.feishu.cn/open-apis/bot/v2/hook/xxx |
| FEISHU_SECRET | 飞书机器人签名密钥 | ❌ | your_secret_key |
| SENTRY_CLIENT_SECRET | Sentry Webhook 验证密钥 | ❌ | your_sentry_secret |
| PORT | 服务监听端口 | ❌ | 8000 |
| DEBUG_MODE | 调试模式 | ❌ | false |

### 高级配置

#### PROJECT_FEISHU_WEBHOOK_MAPPING

**用途**: 配置不同 Sentry 项目到不同飞书群的映射关系

**支持格式**:

1. **JSON 格式**（推荐）:
```bash
# 压缩格式
PROJECT_FEISHU_WEBHOOK_MAPPING='{"1": "https://open.feishu.cn/hook/url1", "项目A": "https://open.feishu.cn/hook/url2"}'

# 格式化格式（支持多行）
PROJECT_FEISHU_WEBHOOK_MAPPING='{
  "1": "https://open.feishu.cn/hook/url1",
  "项目A": "https://open.feishu.cn/hook/url2",
  "2": "https://open.feishu.cn/hook/url3"
}'
```

2. **简单格式**:
```bash
PROJECT_FEISHU_WEBHOOK_MAPPING=1=https://open.feishu.cn/hook/url1,项目A=https://open.feishu.cn/hook/url2
```

**说明**:
- 键可以是项目 ID（数字）或项目名称（字符串）
- 项目 ID 会自动转换为整数进行匹配
- 如果找不到匹配的项目，会使用 `FEISHU_WEBHOOK_URL` 作为默认值
- 如果两者都未配置，该项目的通知将被忽略

#### IGNORE_TO_FEECHU_PROJECT_IDS

**用途**: 配置需要忽略的项目，这些项目的 Sentry 事件不会发送飞书通知

**格式**: JSON 数组，支持项目 ID（数字）和项目名称（字符串）

```bash
# 忽略项目 ID 为 3 和名称为 "项目名称" 的项目
IGNORE_TO_FEECHU_PROJECT_IDS=[3, "项目名称", "test-project"]
```

**使用场景**:
- 测试项目不需要告警
- 某些低优先级项目
- 临时屏蔽某个项目的通知

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
