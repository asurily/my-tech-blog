---
title: OpenClaw 网关核心原理
date: 2026-03-03
tags:
  - OpenClaw
  - 网关
---

[← 返回首页](/index.html)# 写在前面

> 
上一篇文章我们拆解了 OpenClaw 的整体架构，提到了 Gateway（网关）是整个系统的"大脑和心脏"。但具体它是怎么工作的？消息从哪个渠道进来，又是怎么路由到正确的 Agent 的？权限是怎么控制的？

这篇文章，我就带大家深入 Gateway 的内部，完整拆解消息路由、会话管理、权限控制三大核心模块。

---

# 一句话解释网关

**Gateway（网关）** = **消息路由器 + 会话管理器 + 权限控制器 + 技能调度中心**

它是 OpenClaw 的核心枢纽，负责协调所有组件的协作。

---

# 核心架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Gateway                                │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│   │   Router   │  │  Session   │  │   Auth Manager  │   │
│   │   消息路由  │  │   会话管理   │  │    权限控制     │   │
│   └─────────────┘  └─────────────┘  └─────────────────┘   │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│   │   Channel  │  │   Skills   │  │    Memory      │   │
│   │   通道管理  │  │   技能系统  │  │     记忆系统    │   │
│   └─────────────┘  └─────────────┘  └─────────────────┘   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      WebSocket / HTTP                         │
│              openclaw gateway --port 18789                   │
└─────────────────────────────────────────────────────────────────┘
```

---

# 4 大核心模块

## 4.1 消息路由 - Router

**消息路由是 Gateway 的第一道关卡**，决定了一条消息从哪里来、到哪里去。

### 核心职责

|功能
|说明

|消息解析
|将各渠道的原始消息转换为统一格式

|路由匹配
|根据消息来源和内容决定处理方式

|格式转换
|将响应转换为目标渠道的格式

### 路由流程

```
用户发送消息
    │
    ▼
┌─────────────────┐
│  Channel 接收   │  解析消息格式
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Router        │  识别来源渠道、用户ID、消息类型
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Session Key    │  生成会话标识
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Agent         │  转发给 AI 处理
└─────────────────┘
```

### 核心代码

```
// 消息路由器
class Router {
  private channels = new Map<string, Channel>();
  private sessionManager: SessionManager;

  // 注册渠道
  registerChannel(channel: Channel) {
    this.channels.set(channel.name, channel);
  }

  // 处理入口
  async handleMessage(raw: RawMessage): Promise<void> {
    // 1. 解析消息
    const message = this.parse(raw);

    // 2. 生成会话Key
    const sessionKey = this.deriveSessionKey(message);

    // 3. 权限验证
    if (!await this.authManager.check(message.from)) {
      throw new AuthError('未授权用户');
    }

    // 4. 获取会话
    const session = await this.sessionManager.getOrCreate(sessionKey);

    // 5. 转发给 Agent
    await this.agent.process(session, message);
  }

  // 会话Key推导规则
  private deriveSessionKey(message: Message): string {
    const { channel, chatType, peerId } = message;

    if (chatType === 'direct') {
      // DM: agent:<agentId>:<channel>:dm:<peerId>
      return `agent:main:${channel}:dm:${peerId}`;
    } else if (chatType === 'group') {
      // 群聊: agent:<agentId>:<channel>:group:<groupId>
      return `agent:main:${channel}:group:${message.groupId}`;
    }

    return `agent:main:${channel}:${peerId}`;
  }
}
```

### 路由配置示例

```
# openclaw.yaml
gateway:
  router:
    # 默认Agent
    defaultAgent: main
    
    # 渠道映射
    channelMapping:
      feishu: main
      telegram: main
      whatsapp: main
    
    # 群聊处理策略
    groupPolicy:
      # 是否自动创建群聊会话
      autoCreate: true
      # 群聊消息是否进入主会话
      collapseToMain: false
```

---

## 4.2 会话管理 - Session Manager

**会话管理是 OpenClaw 的记忆核心**，负责维护每个对话的上下文状态。

### 三层会话结构

|层级
|存储
|生命周期

|内存会话
|RAM
|当前连接期间

|文件会话
|JSONL
|长期保存

|压缩会话
|SQLite
|自动合并

### 会话Key规则

```
# 直接消息 (DM)
agent:<agentId>:main                    # 默认：所有DM共享
agent:<agentId>:<channel>:dm:<peerId>   # per-peer：按用户隔离
agent:<agentId>:<channel>:dm:<peerId>   # per-channel-peer：按渠道+用户隔离

# 群聊
agent:<agentId>:<channel>:group:<groupId>

# 特殊场景
cron:<job.id>                           # 定时任务
hook:<uuid>                             # Webhook
```

### 安全 DM 模式

> 
⚠️ **重要安全建议**：如果你的 Agent 可以接收多个人的 DM，务必启用安全 DM 模式！

```
{
  session: {
    // 安全模式：按渠道+用户隔离会话
    dmScope: "per-channel-peer"
  }
}
```

**为什么要这样做？**

- 默认情况下，所有 DM 共享同一个会话上下文

- Alice 问了你一个私人问题

- Bob 问"我们刚才聊了什么？"

- 如果共享会话，模型可能用 Alice 的上下文回答 Bob！

### 核心代码

```
// 会话管理器
class SessionManager {
  private sessions = new Map<string, Session>();
  private storePath: string;

  // 获取或创建会话
  async getOrCreate(key: SessionKey): Promise<Session> {
    // 1. 尝试从内存获取
    let session = this.sessions.get(key);
    if (session) {
      return session;
    }

    // 2. 从磁盘加载
    session = await this.loadFromDisk(key);
    if (session) {
      this.sessions.set(key, session);
      return session;
    }

    // 3. 创建新会话
    session = this.createNew(key);
    this.sessions.set(key, session);
    return session;
  }

  // 添加消息到会话
  async addMessage(key: SessionKey, message: Message): Promise<void> {
    const session = await this.getOrCreate(key);
    
    // 添加到内存
    session.messages.push(message);
    
    // 追加到磁盘 (JSONL 格式)
    await this.appendToFile(key, message);
    
    // 检查是否需要压缩
    if (session.shouldCompact()) {
      await this.compact(session);
    }
  }

  // 会话压缩
  async compact(session: Session): Promise<void> {
    // 1. 提取系统级重要信息
    const summary = await this.summarize(session.messages);
    
    // 2. 保留最近 N 条消息
    const recent = session.messages.slice(-20);
    
    // 3. 创建压缩后的会话
    const compacted = new Session({
      ...session,
      messages: [
        { role: 'system', content: `会话摘要: ${summary}` },
        ...recent
      ]
    });
    
    // 4. 保存压缩版本
    await this.save(session.key, compacted);
  }
}
```

### 会话存储

```
# 存储路径
# ~/.openclaw/agents/<agentId>/sessions/

# 会话索引
sessions.json

# 会话记录 (JSONL)
<SessionId>.jsonl
```

---

## 4.3 权限控制 - Auth Manager

**权限控制是 Gateway 的安全大门**，确保只有授权用户才能使用 Agent。

### 权限模型

|层级
|控制粒度
|配置方式

|全局
|整个 Gateway
|`gateway.auth.token`

|渠道
|单个渠道
|`channels.<name>.allowedUsers`

|Agent
|单个 Agent
|`agents.<name>.allowedUsers`

### 支持的认证方式

```
┌─────────────────────────────────────┐
│           认证方式                    │
├─────────────────────────────────────┤
│ 1. Token 认证                        │
│    - gateway.auth.token              │
│    - 静态token，简单直接             │
├─────────────────────────────────────┤
│ 2. 密码认证                          │
│    - gateway.auth.password           │
│    - 适合简单场景                    │
├─────────────────────────────────────┤
│ 3. DM 白名单                        │
│    - session.allowList               │
│    - 只有白名单用户可发起 DM         │
├─────────────────────────────────────┤
│ 4. 群聊黑名单                        │
│    - session.groupDenyList           │
│    - 特定群聊可被屏蔽               │
└─────────────────────────────────────┘
```

### 核心代码

```
// 权限管理器
class AuthManager {
  private config: AuthConfig;

  // 验证用户权限
  async verify(user: UserContext): Promise<AuthResult> {
    // 1. 全局 Token 验证
    if (this.config.token) {
      if (user.token !== this.config.token) {
        return { allowed: false, reason: 'invalid_token' };
      }
    }

    // 2. DM 白名单验证
    if (this.config.allowList?.enabled) {
      const isAllowed = this.config.allowList.users.includes(user.id);
      if (!isAllowed) {
        return { allowed: false, reason: 'not_in_allowlist' };
      }
    }

    // 3. 群聊黑名单验证
    if (user.chatType === 'group') {
      const isDenied = this.config.denyList?.groups.includes(user.groupId);
      if (isDenied) {
        return { allowed: false, reason: 'in_denylist' };
      }
    }

    return { allowed: true };
  }

  // 获取用户权限级别
  getPermissionLevel(user: UserContext): PermissionLevel {
    if (this.config.admins?.includes(user.id)) {
      return 'admin';
    }
    if (this.config.powerUsers?.includes(user.id)) {
      return 'power';
    }
    return 'user';
  }
}
```

### 配置示例

```
# openclaw.yaml
gateway:
  auth:
    # 方式1: Token 认证
    token: ${OPENCLAW_GATEWAY_TOKEN}
    
    # 方式2: 密码认证
    password: ${OPENCLAW_GATEWAY_PASSWORD}

session:
  # DM 白名单 (安全模式)
  allowList:
    enabled: true
    users:
      - user_id_1
      - user_id_2

  # 群聊黑名单
  groupDenyList:
    - group_id_1
    - group_id_2
```

### 权限命令

```
# 检查安全设置
openclaw security audit

# 查看当前权限配置
openclaw gateway status
```

---

# 消息流转完整流程

```
                    用户发送消息
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  1. Channel 接收                                              │
│     - 解析原始消息 (JSON/REST/WebSocket)                     │
│     - 转换为统一 Message 格式                                  │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  2. Router 路由                                               │
│     - 识别渠道、用户ID、消息类型                               │
│     - 推导 Session Key                                        │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  3. Auth 权限验证                                             │
│     - Token 验证                                              │
│     - 白名单/黑名单检查                                        │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  4. Session Manager                                          │
│     - 获取/创建会话                                           │
│     - 添加消息到上下文                                         │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  5. Memory Manager                                           │
│     - 检索相关记忆                                            │
│     - 构建完整 Prompt                                          │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  6. Agent (LLM + Tools)                                      │
│     - 调用大模型                                              │
│     - 执行工具                                                │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  7. Session Manager                                          │
│     - 保存到长期记忆                                          │
│     - 压缩（如需要）                                           │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  8. Router + Channel                                          │
│     - 路由响应到原渠道                                        │
│     - 格式转换                                                │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
                    用户收到回复
```

---

# 实战：配置网关

## 步骤 1: 启动网关

```
# 基本启动
openclaw gateway --port 18789

# 调试模式 (查看详细日志)
openclaw gateway --port 18789 --verbose

# 强制启动 (终止占用端口的进程)
openclaw gateway --port 18789 --force

# 开发模式 (热重载)
pnpm gateway:watch
```

## 步骤 2: 配置权限

```
# ~/.openclaw/openclaw.json
{
  "gateway": {
    "auth": {
      "token": "your-secret-token"
    }
  },
  "session": {
    "allowList": {
      "enabled": true,
      "users": ["user_123", "user_456"]
    }
  }
}
```

## 步骤 3: 配置会话策略

```
# DM 会话隔离策略
session:
  # 选项: main / per-peer / per-channel-peer
  dmScope: "per-channel-peer"
  
  # 主会话 Key
  mainKey: "main"
```

## 步骤 4: 验证配置

```
# 检查网关状态
openclaw gateway status

# 安全审计
openclaw security audit

# 查看健康状态
openclaw health --json
```

---

# 对比：不同网关方案的差异

|特性
|OpenClaw Gateway
|自建方案
|商业方案

|多渠道支持
|开箱即用
|需自行开发
|需付费

|本地部署
|✅
|✅
|❌

|会话管理
|自动压缩/记忆
|需自行实现
|部分支持

|权限控制
|白名单/黑名单
|需自行实现
|部分支持

|成本
|开源免费
|人力成本
|订阅费用

|扩展性
|插件化
|完全可控
|受限

---

# 总结

网关是 OpenClaw 的核心枢纽，承担了四大职责：

- **消息路由** - 统一处理多渠道消息

- **会话管理** - 维护对话上下文，支持自动压缩

- **权限控制** - Token/白名单/黑名单多层保护

- **技能调度** - 协调 Skills 和 Agent 的交互

通过这篇文章，你应该对 Gateway 的内部工作原理有了全面了解。下一篇文章我们将深入 **Channel 通道系统**，看看 OpenClaw 是如何支持这么多即时通讯平台的。

---

*下篇预告：《Channel 通道系统 - 多渠道接入原理与飞书/Telegram 示例》，敬请期待。*
