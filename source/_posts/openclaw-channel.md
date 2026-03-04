---
title: OpenClaw Channel 通道系统
date: 2026-03-03
tags:
  - OpenClaw
  - Channel
---

[← 返回首页](/index.html)# 写在前面

> 
上一篇文章我们深入了解了 Gateway 的内部原理，知道消息是如何路由、会话是如何管理的。但还有一个关键问题：OpenClaw 是怎么跟各种聊天工具（飞书、Telegram、WhatsApp 等）连接的？

这篇文章，我就带大家深入 **Channel 通道系统**，完整拆解多渠道接入的原理，并详细讲解飞书和 Telegram 的配置示例。

---

# 一句话解释通道系统

**Channel（通道）** = **消息适配器**

它将各平台不同的协议、格式、Webhook 统一转换为 OpenClaw 内部的标准消息格式。

---

# 支持的渠道一览

|类别
|渠道
|协议
|状态

|即时通讯
|WhatsApp
|Baileys (WebSocket)
|原生支持

|
|Telegram
|Bot API (HTTP)
|原生支持

|
|Discord
|Gateway + HTTP
|原生支持

|
|Signal
|signal-cli
|插件

|企业协作
|飞书
|WebSocket
|插件

|
|钉钉
|Webhook
|插件

|
|Slack
|Bolt SDK
|插件

|
|Microsoft Teams
|Bot Framework
|插件

|Apple
|iMessage
|BlueBubbles API
|插件

|
|SMS
|Twilio
|插件

|去中心化
|Matrix
|Matrix Client-Server
|插件

|
|Nostr
|NIP-04
|插件

---

# 核心架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      消息来源                                  │
│   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐           │
│   │  飞书  │  │Telegram│  │WhatsApp│  │Discord │   ...    │
│   └────┬───┘  └────┬───┘  └────┬───┘  └────┬───┘           │
│        │           │           │           │                  │
│        ▼           ▼           ▼           ▼                  │
│   ┌─────────────────────────────────────────────────────┐   │
│   │               Channel Adapter                        │   │
│   │   ┌─────────┐  ┌─────────┐  ┌─────────┐             │   │
│   │   │ Parser  │→ │ Normalizer│→│  Router │             │   │
│   │   │ 消息解析 │  │ 格式标准化 │  │ 路由分发 │             │   │
│   │   └─────────┘  └─────────┘  └─────────┘             │   │
│   └────────────────────────┬────────────────────────────┘   │
│                            │                                  │
│                            ▼                                  │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                  Gateway                             │   │
│   │               (统一消息总线)                          │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

# 4 大核心模块

## 4.1 Channel 抽象层

**Channel 是 OpenClaw 与外部世界连接的桥梁**，每个渠道都是一个独立的 Channel 实现。

### Channel 接口

```
// Channel 抽象基类
abstract class Channel {
  // 渠道名称
  abstract readonly name: string;

  // 支持的能力
  abstract readonly capabilities: ChannelCapability[];

  // 消息处理
  abstract onMessage(handler: MessageHandler): void;

  // 发送消息
  abstract send(to: string, content: MessageContent): Promise<void>;

  // 消息格式转换
  abstract parse(raw: any): Message;
  abstract format(message: Message): any;
}

// 消息能力枚举
enum ChannelCapability {
  Text = 'text',
  Image = 'image',
  Video = 'video',
  Audio = 'audio',
  File = 'file',
  Card = 'card',        // 富文本卡片
  Interactive = 'interactive',  // 交互组件
  Reaction = 'reaction'  // 表情反应
}
```

### 统一消息格式

```
// OpenClaw 内部统一消息格式
interface Message {
  // 消息ID
  id: string;

  // 渠道标识
  channel: string;

  // 聊天类型
  chatType: 'direct' | 'group' | 'channel';

  // 发送者
  sender: {
    id: string;
    name?: string;
    avatar?: string;
  };

  // 接收者 (群聊时为群ID)
  peerId: string;

  // 群ID (如果是群消息)
  groupId?: string;

  // 消息内容
  content: {
    // 文本内容
    text?: string;
    // 图片
    image?: { url: string; mimeType: string };
    // 文件
    file?: { url: string; name: string; mimeType: string };
    // 引用回复
    quote?: string;
  };

  // 元数据
  metadata: {
    timestamp: number;
    raw?: any;
  };
}
```

---

## 4.2 飞书 Channel 实现

飞书是 OpenClaw 在国内最常用的渠道之一，通过 WebSocket 实时接收消息。

### 配置步骤

<h4>步骤 1: 创建飞书应用</h4>

- 打开 [飞书开放平台](https://open.feishu.cn/)

- 创建企业自建应用

- 获取 `App ID` 和 `App Secret`

<img src="/images/feishu-step2-create-app.png" alt="飞书创建应用">

<h4>步骤 2: 配置权限</h4>
需要以下权限：

- `im:message:readonly` - 读取消息

- `im:message:send_as_bot` - 以机器人身份发送消息

- `im:chat:readonly` - 读取群聊信息

- `im:chat:update_others` - 更新群聊信息

<img src="/images/feishu-step4-permissions.png" alt="飞书权限配置">

<h4>步骤 3: 添加机器人到群聊</h4>

- 在飞书中创建群聊

- 添加机器人到群聊

- 获取群聊 ID

### 代码实现

```
// 飞书 Channel
class FeishuChannel extends Channel {
  readonly name = 'feishu';
  readonly capabilities = [
    ChannelCapability.Text,
    ChannelCapability.Image,
    ChannelCapability.Card,
    ChannelCapability.Interactive
  ];

  private app: FeishuApp;
  private handler?: MessageHandler;

  constructor(config: FeishuConfig) {
    super();
    this.app = new FeishuApp(config.appId, config.appSecret);
  }

  // 初始化 (建立 WebSocket 连接)
  async init(): Promise<void> {
    // 1. 获取 WebSocket URL
    const wsUrl = await this.app.getWebSocketUrl();

    // 2. 建立连接
    this.ws = new WebSocket(wsUrl);

    // 3. 处理消息
    this.ws.on('message', (data) => {
      this.handleRawMessage(data);
    });
  }

  // 处理原始消息
  private async handleRawMessage(raw: any): Promise<void> {
    // 飞书消息类型过滤
    if (raw.type !== 'im.message') return;

    const message = this.parse(raw);
    if (this.handler && message) {
      const response = await this.handler(message);
      await this.send(message.sender.id, response);
    }
  }

  // 解析飞书消息
  parse(raw: any): Message {
    const event = raw.event;
    const message = event.message;

    return {
      id: message.message_id,
      channel: 'feishu',
      chatType: event.chat_id ? 'group' : 'direct',
      sender: {
        id: event.sender.sender_id.user_id,
        name: event.sender.sender_id.user_id
      },
      peerId: event.chat_id || event.sender.sender_id.user_id,
      groupId: event.chat_id,
      content: {
        text: message.body?.content
      },
      metadata: {
        timestamp: message.create_time,
        raw: event
      }
    };
  }

  // 发送消息 (支持富文本卡片)
  async send(to: string, content: MessageContent): Promise<void> {
    const card = this.buildCard(content);
    await this.app.sendCard(to, card);
  }

  // 构建飞书卡片消息
  private buildCard(content: MessageContent): object {
    return {
      header: {
        title: {
          tag: 'plain_text',
          content: '🤖 AI 助手'
        },
        template: 'blue'
      },
      elements: [
        {
          tag: 'markdown',
          content: content.text
        }
      ]
    };
  }
}
```

### 配置示例

```
# openclaw.yaml
channels:
  feishu:
    enabled: true
    app_id: ${FEISHU_APP_ID}
    app_secret: ${FEISHU_APP_SECRET}
    
    # 事件验证 token (用于 WebHook 验证)
    verification_token: ${FEISHU_VERIFICATION_TOKEN}
    
    # 加密密钥 (如果开启了encrypt)
    encrypt_key: ${FEISHU_ENCRYPT_KEY}
```

---

## 4.3 Telegram Channel 实现

Telegram 是最简单好用的渠道之一，只需要一个 Bot Token 即可。

### 配置步骤

<h4>步骤 1: 创建 Bot</h4>

- 在 Telegram 中搜索 @BotFather

- 发送 `/newbot` 创建新机器人

- 获取 Bot Token

<h4>步骤 2: 配置 OpenClaw</h4>
```
# openclaw.yaml
channels:
  telegram:
    enabled: true
    bot_token: ${TELEGRAM_BOT_TOKEN}
    
    # 允许的群组 (可选)
    allowed_groups:
      - -123456789
      
    # 是否支持群聊
    allow_groups: true
```

### 代码实现

```
// Telegram Channel (基于 grammY)
class TelegramChannel extends Channel {
  readonly name = 'telegram';
  readonly capabilities = [
    ChannelCapability.Text,
    ChannelCapability.Image,
    ChannelCapability.Video,
    ChannelCapability.Audio,
    ChannelCapability.File,
    ChannelCapability.Card,
    ChannelCapability.Reaction
  ];

  private bot: Bot;
  private handler?: MessageHandler;

  constructor(config: TelegramConfig) {
    super();
    this.bot = new Bot(config.bot_token);
  }

  // 初始化
  async init(): Promise<void> {
    // 使用 grammY 的 long polling
    this.bot.use(this.middleware.bind(this));

    // 启动机器人
    await this.bot.start();
  }

  // 中间件处理
  private async middleware(ctx: Context, next: () => Promise<void>): Promise<void> {
    // 忽略非消息类型
    if (!ctx.message) {
      return next();
    }

    // 转换为统一格式
    const message = this.parse(ctx);

    // 调用处理器
    if (this.handler) {
      const response = await this.handler(message);

      // 发送回复
      if (response) {
        await ctx.reply(response.content.text || '', {
          reply_to_message_id: ctx.message.message_id
        });
      }
    }

    await next();
  }

  // 解析 Telegram 消息
  parse(ctx: Context): Message {
    const msg = ctx.message!;

    return {
      id: String(msg.message_id),
      channel: 'telegram',
      chatType: msg.chat.type === 'private' ? 'direct' : 'group',
      sender: {
        id: String(msg.from?.id),
        name: msg.from?.first_name
      },
      peerId: String(msg.chat.id),
      groupId: msg.chat.type === 'group' || msg.chat.type === 'supergroup'
        ? String(msg.chat.id)
        : undefined,
      content: {
        text: msg.text || msg.caption
      },
      metadata: {
        timestamp: msg.date * 1000,
        raw: msg
      }
    };
  }

  // 发送消息
  async send(to: string, content: MessageContent): Promise<void> {
    await this.bot.api.sendMessage(Number(to), content.text || '');
  }
}
```

---

## 4.4 消息路由与群聊管理

### 群聊消息处理

```
┌─────────────────────────────────────────────────────────────┐
│                    群聊消息路由                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   用户在群聊 @机器人                                         │
│          │                                                  │
│          ▼                                                  │
│   ┌─────────────────┐                                       │
│   │  检测 @mention  │  ──→ 未 @机器人 → 忽略               │
│   └────────┬────────┘                                       │
│            │                                                 │
│            ▼                                                 │
│   ┌─────────────────┐                                       │
│   │  检查黑名单    │  ──→ 在黑名单 → 忽略                   │
│   └────────┬────────┘                                       │
│            │                                                 │
│            ▼                                                 │
│   ┌─────────────────┐                                       │
│   │  创建/获取会话  │                                       │
│   └────────┬────────┘                                       │
│            │                                                 │
│            ▼                                                 │
│   ┌─────────────────┐                                       │
│   │  调用 Agent    │                                       │
│   └────────┬────────┘                                       │
│            │                                                 │
│            ▼                                                 │
│   ┌─────────────────┐                                       │
│   │  发送回复      │                                       │
│   └─────────────────┘                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 配置群聊策略

```
# openclaw.yaml
channels:
  telegram:
    enabled: true
    bot_token: ${TELEGRAM_BOT_TOKEN}
    
    # 群聊处理
    group:
      # 是否启用
      enabled: true
      
      # 回复模式: reply / mention / always
      reply_mode: "reply"
      
      # 响应关键词
      trigger_keywords:
        - "@BotName"
        - "bot:"
        
      # 忽略的群聊ID
      ignore_groups:
        - -1001234567890
        - -1000987654321
```

---

# 实战：配置多渠道

## 步骤 1: 安装飞书插件

```
# 安装飞书 Channel 插件
openclaw plugins install @openclaw/feishu
```

## 步骤 2: 配置环境变量

```
# .env
# 飞书
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
```

## 步骤 3: 配置 openclaw.yaml

```
# openclaw.yaml
channels:
  feishu:
    enabled: true
    app_id: ${FEISHU_APP_ID}
    app_secret: ${FEISHU_APP_SECRET}
    
  telegram:
    enabled: true
    bot_token: ${TELEGRAM_BOT_TOKEN}
    
  whatsapp:
    enabled: false  # 暂时禁用
```

## 步骤 4: 启动并验证

```
# 启动网关
openclaw gateway start

# 查看连接状态
openclaw status

# 发送测试消息
openclaw message send --target <user_id> --message "Hello from OpenClaw!"
```

---

# 对比：主流 Channel 方案

|特性
|OpenClaw Channel
|Bot API
|Webhook Only

|实时消息
|✅ WebSocket
|✅ Long Polling
|❌

|发送图片
|✅
|✅
|✅

|群聊管理
|✅
|✅
|受限

|交互组件
|✅
|✅
|受限

|部署复杂度
|中
|低
|低

|费用
|免费
|免费
|免费

---

# 总结

Channel 系统是 OpenClaw 连接外部世界的桥梁：

- **统一抽象** - 无论什么渠道，都转换为统一消息格式

- **插件化设计** - 轻松添加新渠道支持

- **飞书** - 通过 WebSocket 实时接收消息，支持卡片消息

- **Telegram** - 最简单的配置，支持完整的消息类型

- **群聊管理** - 支持黑名单、关键词触发等策略

通过这篇文章，你应该能够配置自己需要的渠道了。下一篇文章我们将深入 **Skills 技能系统**，看看如何扩展 OpenClaw 的能力。

---

*下篇预告：《Skills 技能系统 - 技能定义与自定义技能实战》，敬请期待。*
