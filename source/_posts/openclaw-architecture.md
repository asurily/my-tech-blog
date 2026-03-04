---
title: OpenClaw 整体架构深度解析
date: 2026-03-03
tags:
  - OpenClaw
  - 架构
---

[← 返回首页](/index.html)
        # 写在前面

> 
上一篇文章发出后，有读者问我："OpenClaw 听起来很强大，但它的内部是怎么工作的？Gateway、Agent、Channel 之间是什么关系？"

确实，光知道"能做什么"不够，知道"怎么做到"才更有价值。

这篇文章，我就带大家深入 OpenClaw 的内部世界，从架构设计到代码实现，全面拆解这个 AI 助手框架。

---

# 一句话解释架构

**OpenClaw** = **Gateway（网关）+ Agent（大脑）+ Channel（渠道）+ Skills（技能）+ Memory（记忆）**

五大模块协同工作，构成了一个完整的 AI Agent 系统。

---

# 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Channels                             │
│   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐           │
│   │  Feishu│  │Telegram│  │Discord │  │ WhatsApp│  ...    │
│   └────────┘  └────────┘  └────────┘  └────────┘           │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Gateway                             │
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
│                         Agent                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│   │  Provider   │  │   Tools    │  │   Prompts      │   │
│   │   模型调用   │  │   工具调用   │  │     提示词      │   │
│   └─────────────┘  └─────────────┘  └─────────────────┘   │
└───────────────────────────────────────────────────────────────┘
```

---

# 5 大核心模块

## 1. 网关 - 控制平面 🚀

**网关是整个系统的大脑和心脏**，负责协调所有组件。

### 核心职责

|功能
|说明

|消息路由
|接收 Channel 消息，转发给 Agent

|会话管理
|管理每个用户的对话状态

|权限控制
|验证用户身份和权限

|技能调度
|决定何时调用哪个 Skill

### 核心代码

```
// Gateway 核心逻辑
class 网关 {
  private router: Router;
  private sessionManager: SessionManager;
  private skillManager: SkillManager;
  private memoryManager: MemoryManager;
  private agent: Agent;

  async handleMessage(channel: string, user: string, message: string) {
    // 1. 权限验证
    if (!await this.authManager.verify(user)) {
      throw new AuthError('未授权用户');
    }

    // 2. 获取/创建会话
    const session = await this.sessionManager.getOrCreate({ channel, user });

    // 3. 构建 Prompt（含记忆）
    const prompt = await this.buildPrompt(session, message);

    // 4. 调用 Agent
    const response = await this.agent.complete(prompt);

    // 5. 通过原渠道回复
    await this.channel.send(user, response);
  }

  private async buildPrompt(session: Session, message: string): Promise<Prompt> {
    // 短期记忆：当前会话
    const shortMemory = session.messages;

    // 长期记忆：向量检索
    const longMemory = await this.memory.search(message, { limit: 5 });

    return {
      system: SYSTEM_PROMPT,
      context: longMemory,
      conversation: shortMemory,
      user: message
    };
  }
}
```

---

## 2. Agent - AI 大脑 🧠

**Agent 负责与 AI 模型交互**，是真正的"智能"所在。

### 核心功能

|功能
|说明

|模型调用
|支持 Anthropic/OpenAI/Google 等多种模型

|Tool 选择
|决定调用哪个工具完成请求

|Prompt 管理
|构建和优化提示词

### Provider 抽象

```
// LLM Provider 抽象
abstract class LLMProvider {
  abstract readonly name: string;
  abstract complete(prompt: Prompt): Promise<LLMResponse>;
  abstract *completeStream(prompt: Prompt): AsyncGenerator<Chunk>;
  abstract completeWithFunctions(prompt: Prompt, tools: Tool[]): Promise<FunctionCall>;
}

// Anthropic 实现
class AnthropicProvider extends LLMProvider {
  readonly name = 'anthropic';

  async complete(prompt: Prompt): Promise<LLMResponse> {
    const response = await this.client.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      system: prompt.system,
      messages: [
        ...prompt.context.map(c => ({ role: 'assistant', content: c.content })),
        { role: 'user', content: prompt.user }
      ]
    });

    return {
      content: response.content[0].text,
      usage: {
        input: response.usage.input_tokens,
        output: response.usage.output_tokens
      }
    };
  }
}
```

### 模型配置

```
# openclaw.yaml
models:
  primary:
    provider: anthropic
    model: claude-sonnet-4-20250514
    api_key: ${ANTHROPIC_API_KEY}
  
  fallback:
    provider: openai
    model: gpt-4o
    api_key: ${OPENAI_API_KEY}
```

---

## 3. Channel - 消息通道 📱

**Channel 是 OpenClaw 与外部世界连接的桥梁**。

### 支持的渠道

|类别
|渠道

|即时通讯
|微信、Telegram、Discord、Slack、Signal、iMessage

|企业协作
|飞书、钉钉、Microsoft Teams

|其他
|Matrix、BlueBubbles

### Channel 抽象

```
// Channel 抽象基类
abstract class Channel {
  abstract readonly name: string;
  abstract readonly capabilities: ChannelCapability[];

  // 接收消息
  abstract onMessage(handler: MessageHandler): void;

  // 发送消息
  abstract send(to: string, content: MessageContent): Promise<void>;

  // 消息格式转换
  abstract parse(raw: any): Message;
  abstract format(message: Message): any;
}
```

### 飞书 Channel 示例

```
// 飞书消息处理
class FeishuChannel extends Channel {
  readonly name = 'feishu';
  readonly capabilities = ['text', 'image', 'card', 'interactive'];

  private app: FeishuApp;

  constructor(config: FeishuConfig) {
    super();
    this.app = new FeishuApp(config.appId, config.appSecret);
  }

  // 接收消息
  onMessage(handler: MessageHandler): void {
    this.app.on('message', async (event) => {
      const message = this.parse(event);
      const response = await handler(message);
      await this.send(event.sender.user_id, response);
    });
  }

  // 发送卡片消息
  async send(to: string, content: MessageContent): Promise<void> {
    const card = {
      header: {
        title: { tag: 'plain_text', content: '🤖 AI 助手' },
        template: 'blue'
      },
      elements: [
        { tag: 'markdown', content: content.text }
      ]
    };
    await this.app.sendCard(to, card);
  }
}
```

### 配置示例

```
channels:
  feishu:
    enabled: true
    app_id: ${FEISHU_APP_ID}
    app_secret: ${FEISHU_APP_SECRET}

  telegram:
    enabled: true
    bot_token: ${TELEGRAM_BOT_TOKEN}
```

---

## 4. Skills - 技能系统 🛠️

**Skills 是 OpenClaw 的扩展机制**，让你能无限扩展 AI 的能力。

### Skill 结构

```
interface Skill {
  readonly name: string;
  readonly description: string;
  readonly version: string;

  // 初始化
  init(context: SkillContext): Promise<void>;

  // 注册工具
  registerTools(): Tool[];

  // 处理消息（可选）
  handle?(message: Message): Promise<HandleResult>;
}
```

### 天气 Skill 示例

```
class WeatherSkill implements Skill {
  readonly name = 'weather';
  readonly description = '查询天气信息';
  readonly version = '1.0.0';

  private apiKey: string;

  constructor(config: WeatherConfig) {
    this.apiKey = config.apiKey;
  }

  async init(): Promise<void> {
    console.log('🌤️ Weather skill initialized');
  }

  registerTools(): Tool[] {
    return [
      {
        name: 'get_weather',
        description: '获取指定城市的天气信息',
        parameters: {
          type: 'object',
          properties: {
            city: {
              type: 'string',
              description: '城市名称，如北京、上海'
            }
          },
          required: ['city']
        }
      }
    ];
  }

  // 工具实现
  async getWeather(city: string): Promise<WeatherResult> {
    const response = await fetch(
      `https://api.weather.com/v3/forecast?city=${city}&key=${this.apiKey}`
    );
    return response.json();
  }
}
```

### Skill 加载

```
class SkillManager {
  private skills = new Map<string, Skill>();

  async loadSkills(skillDirs: string[]): Promise<void> {
    for (const dir of skillDirs) {
      // 动态加载
      const skill = await this.importSkill(dir);

      // 初始化
      await skill.init(this.createContext());

      // 注册工具到 Agent
      const tools = skill.registerTools();
      this.agent.registerTools(tools);

      this.skills.set(skill.name, skill);
    }
  }
}
```

### 官方 Skills

|Skill
|功能

|weather
|天气查询

|xiaohongshu-generator
|小红书推文生成

|qqbot-cron
|定时提醒

|calendar
|日历管理

---

## 5. Memory - 记忆系统 💾

**Memory 让 OpenClaw 能"记住"之前说过的话**。

### 三层记忆架构

```
┌─────────────────────────────────────┐
│           短期记忆                    │
│     (当前会话上下文，内存中)          │
│     session.messages                │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│           长期记忆                    │
│    (向量数据库，持久化存储)          │
│    LanceDB / SQLite                 │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│           文件记忆                    │
│    (从文件系统读取上下文)            │
│    workspace/*.md                    │
└─────────────────────────────────────┘
```

### Memory Manager

```
class MemoryManager {
  // 短期记忆
  private shortTerm = new ShortTermMemory();

  // 长期记忆（向量）
  private longTerm = new LanceDBMemory();

  // 文件记忆
  private fileMemory = new FileMemory();

  // 搜索记忆
  async search(query: string, options: SearchOptions): Promise<MemoryResult[]> {
    // 1. 向量检索
    const vectorResults = await this.longTerm.search(query, {
      limit: options.limit || 5
    });

    // 2. 文件检索
    const fileResults = await this.fileMemory.search(query);

    // 3. 合并结果
    return this.mergeResults(vectorResults, fileResults);
  }

  // 保存会话到长期记忆
  async saveSession(session: Session): Promise<void> {
    const embeddings = await this.embed(session.messages);
    await this.longTerm.save({
      id: session.id,
      embeddings,
      metadata: {
        channel: session.channel,
        user: session.user,
        timestamp: Date.now()
      }
    });
  }
}
```

### 配置示例

```
memory:
  short_term:
    max_messages: 100
    ttl: 3600000  # 1小时

  long_term:
    enabled: true
    provider: lancedb
    path: ./data/memory

  file_memory:
    enabled: true
    paths:
      - ./workspace
      - ./memory
```

---

# 消息流转完整流程

```
用户发送消息
    │
    ▼
┌─────────────────┐
│   Channel      │ 接收消息，解析格式
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Gateway     │ 权限验证
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Session Manager │ 获取/创建会话
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Memory Manager  │ 检索相关记忆
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Agent       │ 调用 LLM + Tools
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Memory Manager  │ 保存到长期记忆
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Gateway     │ 路由到原 Channel
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Channel      │ 发送回复
└─────────────────┘
         │
         ▼
    用户收到回复
```

---

# 总结

OpenClaw 的架构设计体现了几个核心思想：

- **分层解耦** - Gateway、Agent、Channel、Skills、Memory 各自独立

- **可扩展** - Skill 和 Channel 都是插件化设计

- **本地优先** - 数据本地存储，尊重隐私

- **多渠道统一** - 统一的消息抽象，屏蔽各渠道差异

这种架构使得 OpenClaw 不仅仅是一个聊天工具，而是一个**可定制的 AI Agent 平台**。

---

*下篇预告：《Channel 通道系统实现原理》，敬请期待。*
