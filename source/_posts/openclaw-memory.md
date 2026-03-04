---
title: OpenClaw Memory 记忆系统
date: 2026-03-03
tags:
  - OpenClaw
  - 记忆系统
---

[← 返回首页](/index.html)# 写在前面

> 
有读者问："ChatGPT 每次都是全新对话，OpenClaw 怎么能'记住'之前说过的话？"

这篇就来讲讲 **Memory 记忆系统**，看看 OpenClaw 是如何实现短期、长期、文件三层记忆的。

---

# 一句话解释 Memory

**Memory** = OpenClaw 的**记忆系统**，让 AI 能"记住"之前说过的话。

---

# 三层记忆架构

```
┌─────────────────────────────────────┐
│           短期记忆                    │
│     (当前会话上下文，内存中)          │
│     session.messages                │
│     ~50-100 条对话                  │
└─────────────────┬───────────────────┘
                  │
                  ▼ 超过阈值时写入
┌─────────────────────────────────────┐
│           长期记忆                    │
│    (向量数据库，持久化存储)          │
│    LanceDB / SQLite                 │
│    语义搜索，支持相似度匹配          │
└─────────────────┬───────────────────┘
                  │
                  ▼ 按需读取
┌─────────────────────────────────────┐
│           文件记忆                    │
│    (从文件系统读取上下文)            │
│    workspace/*.md                   │
│    TOOLS.md, MEMORY.md 等          │
└─────────────────────────────────────┘
```

---

# 短期记忆

## 1. 会话消息存储

```
class ShortTermMemory {
  private messages: Message[] = [];
  private maxMessages: number = 100;

  // 添加消息
  add(role: 'user' | 'assistant' | 'system', content: string): void {
    this.messages.push({
      role,
      content,
      timestamp: Date.now()
    });

    // 超过上限，删除最老的
    if (this.messages.length > this.maxMessages) {
      this.messages.shift();
    }
  }

  // 获取最近 N 条
  getRecent(limit: number = 50): Message[] {
    return this.messages.slice(-limit);
  }

  // 清空
  clear(): void {
    this.messages = [];
  }
}
```

## 2. 会话管理

```
class Session {
  readonly id: string;
  readonly channel: string;
  readonly user: string;
  memory: ShortTermMemory;
  lastActive: number;

  constructor(opts: SessionOptions) {
    this.id = crypto.randomUUID();
    this.channel = opts.channel;
    this.user = opts.user;
    this.memory = new ShortTermMemory();
    this.lastActive = Date.now();
  }

  // 添加用户消息
  addUserMessage(content: string): void {
    this.memory.add('user', content);
    this.lastActive = Date.now();
  }

  // 添加 AI 回复
  addAssistantMessage(content: string): void {
    this.memory.add('assistant', content);
    this.lastActive = Date.now();
  }
}
```

---

# 长期记忆

## 1. 向量存储

```
class LongTermMemory {
  private db: LanceDB;
  private embedding: EmbeddingModel;

  async init(config: MemoryConfig): Promise<void> {
    this.db = await LanceDB.load(config.path);
    this.embedding = new EmbeddingModel(config.embeddingModel);
  }

  // 保存到记忆
  async save(session: Session): Promise<void> {
    // 1. 会话消息转为文本
    const text = session.memory.getRecent(20)
      .map(m => `${m.role}: ${m.content}`)
      .join('\n');

    // 2. 生成向量
    const vector = await this.embedding.embed(text);

    // 3. 写入数据库
    await this.db.insert('memories', {
      id: session.id,
      user: session.user,
      channel: session.channel,
      text,
      vector,
      timestamp: Date.now()
    });
  }

  // 搜索记忆
  async search(query: string, options: SearchOptions = {}): Promise<MemoryResult[]> {
    const { limit = 5, threshold = 0.7 } = options;

    // 1. 查询文本转向量
    const queryVector = await this.embedding.embed(query);

    // 2. 向量相似度搜索
    const results = await this.db.query('memories', {
      vector: queryVector,
      k: limit,
      threshold
    });

    // 3. 返回结果
    return results.map(r => ({
      id: r.id,
      text: r.text,
      score: r.score,
      timestamp: r.timestamp
    }));
  }
}
```

## 2. Embedding 模型

```
interface EmbeddingModel {
  embed(text: string): Promise<number[]>;
}

class OpenAIEmbedding implements EmbeddingModel {
  private client: OpenAI;

  async embed(text: string): Promise<number[]> {
    const response = await this.client.embeddings.create({
      model: 'text-embedding-3-small',
      input: text
    });

    return response.data[0].embedding;
  }
}

class AnthropicEmbedding implements EmbeddingModel {
  // Anthropic 没有官方 Embedding API
  // 可使用第三方或本地模型
}
```

---

# 文件记忆

## 1. 文件加载

```
class FileMemory {
  private paths: string[] = [];
  private cache = new Map<string, string>();

  constructor(paths: string[]) {
    this.paths = paths;
  }

  // 加载所有文件
  async load(): Promise<void> {
    for (const path of this.paths) {
      const files = await glob(`${path}/**/*.md`);
      for (const file of files) {
        const content = await fs.readFile(file, 'utf-8');
        this.cache.set(file, content);
      }
    }
  }

  // 搜索文件内容
  async search(query: string): Promise<FileResult[]> {
    const results: FileResult[] = [];

    for (const [file, content] of this.cache) {
      // 简单关键词匹配
      if (content.toLowerCase().includes(query.toLowerCase())) {
        // 提取相关段落
        const snippets = this.extractSnippets(content, query);
        results.push({
          file,
          snippets
        });
      }
    }

    return results;
  }

  private extractSnippets(content: string, query: string): string[] {
    const snippets: string[] = [];
    const lines = content.split('\n');

    for (let i = 0; i < lines.length; i++) {
      if (lines[i].toLowerCase().includes(query.toLowerCase())) {
        // 提取前后 3 行
        const start = Math.max(0, i - 3);
        const end = Math.min(lines.length, i + 4);
        snippets.push(lines.slice(start, end).join('\n'));
      }
    }

    return snippets;
  }
}
```

## 2. 常用文件

OpenClaw 会自动加载以下文件作为上下文：

|文件
|用途

|`SOUL.md`
|AI 人设、性格

|`USER.md`
|用户偏好、背景

|`MEMORY.md`
|长期记忆、重要事件

|`TOOLS.md`
|工具配置、API 密钥

|`AGENTS.md`
|工作目录规范

|`memory/YYYY-MM-DD.md`
|每日记录

---

# Memory Manager

## 1. 统一接口

```
class MemoryManager {
  private shortTerm = new ShortTermMemory();
  private longTerm: LongTermMemory;
  private fileMemory: FileMemory;

  constructor(config: MemoryConfig) {
    if (config.longTerm?.enabled) {
      this.longTerm = new LongTermMemory();
    }
    if (config.fileMemory?.enabled) {
      this.fileMemory = new FileMemory(config.fileMemory.paths);
    }
  }

  // 搜索记忆
  async search(query: string, options: SearchOptions = {}): Promise<SearchResult[]> {
    const results: SearchResult[] = [];

    // 1. 长期记忆搜索
    if (this.longTerm) {
      const longResults = await this.longTerm.search(query, options);
      results.push(...longResults.map(r => ({
        type: 'long_term' as const,
        ...r
      })));
    }

    // 2. 文件记忆搜索
    if (this.fileMemory) {
      const fileResults = await this.fileMemory.search(query);
      results.push(...fileResults.map(r => ({
        type: 'file' as const,
        ...r
      })));
    }

    // 3. 按相关性排序
    return results.sort((a, b) => b.score - a.score);
  }

  // 保存会话
  async saveSession(session: Session): Promise<void> {
    // 添加到短期记忆
    session.memory.getRecent(100).forEach(m => {
      this.shortTerm.add(m.role as any, m.content);
    });

    // 定期写入长期记忆
    if (this.longTerm && shouldSaveToLongTerm(session)) {
      await this.longTerm.save(session);
    }
  }
}
```

## 2. 构建 Prompt

```
class PromptBuilder {
  async build(session: Session, message: string): Promise<Prompt> {
    // 1. 短期记忆
    const recentMessages = session.memory.getRecent(20);

    // 2. 长期记忆（语义搜索）
    const longMemory = await memory.search(message, { limit: 5 });

    // 3. 文件记忆
    const fileMemory = await memory.search(message, { limit: 3 });

    // 4. 构建 Prompt
    return {
      system: this.getSystemPrompt(),
      context: [
        ...longMemory.map(m => ({
          role: 'system' as const,
          content: `[记忆] ${m.text}`
        })),
        ...fileMemory.map(f => ({
          role: 'system' as const,
          content: `[文件: ${f.file}]\n${f.snippets.join('\n\n')}`
        }))
      ],
      conversation: recentMessages,
      user: message
    };
  }
}
```

---

# 配置示例

```
memory:
  # 短期记忆
  short_term:
    enabled: true
    max_messages: 100

  # 长期记忆
  long_term:
    enabled: true
    provider: lancedb
    path: ./data/memory
    embedding_model: text-embedding-3-small
    save_interval: 3600000  # 1小时

  # 文件记忆
  file_memory:
    enabled: true
    paths:
      - ./workspace
      - ./memory
    ignore:
      - "*.git/*"
      - "node_modules/*"
```

---

# 总结

Memory 系统核心思想：

- **分层存储** - 短期→长期→文件，层层递进

- **向量搜索** - 语义匹配，不只是关键词

- **自动加载** - 特定文件自动作为上下文

- **按需读取** - 只加载相关的记忆

这就是 OpenClaw 能"记住你之前说过什么"的秘诀。

---

*系列预告：后续还有《Agent 与模型调用》《部署与运维》《最佳实践》等，敬请期待！*
