---
title: OpenClaw Skills 技能系统
date: 2026-03-03
tags:
  - OpenClaw
  - Skills
---

[← 返回首页](/index.html)# 写在前面

> 
有读者问："OpenClaw 怎么做到'上知天文，下知地理'的？天气查询、定时提醒这些功能是怎么实现的？"

这篇就来讲讲 **Skills 技能系统**，看看 OpenClaw 是如何通过 Skills 扩展能力的。

---

# 一句话解释 Skills

**Skills** = OpenClaw 的**插件系统**，让你能无限扩展 AI 的能力。

---

# Skills vs Tools

|
|Skills
|Tools

|概念
|完整的技能包
|单个工具函数

|复杂度
|高（可包含多个 Tools）
|低（单一功能）

|场景
|复杂业务逻辑
|简单函数调用

|示例
|天气 Skill（查询+预报+预警）
|get_weather()

---

# Skill 架构

## 1. Skill 定义

```
interface Skill {
  // 元信息
  readonly name: string;
  readonly description: string;
  readonly version: string;

  // 依赖
  readonly dependencies?: string[];

  // 生命周期
  init(context: SkillContext): Promise<void>;
  destroy(): Promise<void>;

  // 核心功能
  registerTools(): Tool[];

  // 消息处理（可选）
  handle?(message: Message): Promise<HandleResult>;

  // 定时任务（可选）
  cron?: CronJob[];
}

interface SkillContext {
  config: Record<string, any>;
  logger: Logger;
  storage: Storage;
  http: HttpClient;
}
```

## 2. Tool 定义

```
interface Tool {
  // 工具名称
  name: string;

  // 工具描述（用于 LLM 理解何时调用）
  description: string;

  // 参数 schema（JSON Schema）
  parameters: JSONSchema;

  // 是否必需
  required?: string[];
}

interface JSONSchema {
  type: 'object';
  properties: Record<string, {
    type: string;
    description?: string;
    enum?: string[];
  }>;
  required?: string[];
}
```

---

# 天气 Skill 示例

## 1. Skill 实现

```
class WeatherSkill implements Skill {
  readonly name = 'weather';
  readonly description = '查询天气信息，支持全球城市';
  readonly version = '1.0.0';

  private apiKey: string;
  private http: HttpClient;

  constructor(config: WeatherConfig) {
    this.apiKey = config.apiKey;
  }

  async init(context: SkillContext): Promise<void> {
    this.http = context.http;
    console.log('🌤️ Weather skill initialized');
  }

  registerTools(): Tool[] {
    return [
      {
        name: 'get_current_weather',
        description: '获取指定城市的当前天气',
        parameters: {
          type: 'object',
          properties: {
            city: {
              type: 'string',
              description: '城市名称，如北京、上海、Tokyo'
            }
          },
          required: ['city']
        }
      },
      {
        name: 'get_forecast',
        description: '获取天气预报',
        parameters: {
          type: 'object',
          properties: {
            city: { type: 'string', description: '城市名称' },
            days: {
              type: 'number',
              description: '预报天数，1-7',
              enum: [1, 2, 3, 4, 5, 6, 7]
            }
          },
          required: ['city', 'days']
        }
      }
    ];
  }

  // 工具实现
  async getCurrentWeather(city: string): Promise<WeatherResult> {
    const response = await this.http.get(
      `https://api.weather.com/v3/wx/conditions/current`,
      { params: { location: city, apikey: this.apiKey } }
    );

    return {
      city: response.location.city,
      temp: response.temperature,
      condition: response.weather,
      humidity: response.humidity,
      wind: response.wind.speed,
      updateTime: response.observationTime
    };
  }

  async getForecast(city: string, days: number): Promise<ForecastResult[]> {
    const response = await this.http.get(
      `https://api.weather.com/v3/wx/forecast/daily`,
      { params: { location: city, days, apikey: this.apiKey } }
    );

    return response.forecasts.map((f: any) => ({
      date: f.date,
      high: f.temperature.max,
      low: f.temperature.min,
      condition: f.weather
    }));
  }
}
```

## 2. Skill 注册

```
// Skill 工厂
class SkillFactory {
  static create(name: string, config: any): Skill {
    const map: Record<string, any> = {
      'weather': WeatherSkill,
      'cron': CronSkill,
      'notion': NotionSkill
    };

    const SkillClass = map[name];
    if (!SkillClass) {
      throw new Error(`Unknown skill: ${name}`);
    }

    return new SkillClass(config);
  }
}
```

---

# Skills Manager

## 1. 加载 Skills

```
class SkillManager {
  private skills = new Map<string, Skill>();
  private agent: Agent;

  async loadSkills(configs: SkillConfig[]): Promise<void> {
    for (const config of configs) {
      if (!config.enabled) continue;

      // 创建 Skill 实例
      const skill = SkillFactory.create(config.name, config.options);

      // 初始化
      await skill.init(this.createContext());

      // 注册 Tools
      const tools = skill.registerTools();
      this.agent.registerTools(tools);

      // 保存
      this.skills.set(skill.name, skill);
    }
  }

  // 调用 Skill 的工具
  async callTool(name: string, args: Record<string, any>): Promise<any> {
    const skill = this.findSkillByTool(name);
    if (!skill) {
      throw new Error(`Tool not found: ${name}`);
    }

    // 动态调用
    const method = (skill as any)[name];
    if (typeof method !== 'function') {
      throw new Error(`Method not found: ${name}`);
    }

    return await method.call(skill, args);
  }

  private findSkillByTool(toolName: string): Skill | undefined {
    for (const skill of this.skills.values()) {
      const tools = skill.registerTools();
      if (tools.some(t => t.name === toolName)) {
        return skill;
      }
    }
    return undefined;
  }
}
```

---

# 社区 Skills

## 1. 安装 Skills

```
# 安装官方 Skills
openclaw skill install weather
openclaw skill install cron
openclaw skill install notion

# 安装社区 Skills
openclaw skill install xiaohongshu-generator
```

## 2. 官方 Skills 列表

|Skill
|功能
|Tools

|weather
|天气查询
|get_current_weather, get_forecast

|cron
|定时任务
|set_reminder, list_reminders

|notion
|Notion 集成
|create_page, query_database

|xiaohongshu
|小红书生成
|generate_post

|memory
|记忆管理
|search_memory, save_memory

|tts
|语音合成
|speak

---

# 自定义 Skill

## 1. 创建 Skill

```
mkdir -p skills/my-skill
cd skills/my-skill
```

## 2. SKILL.md 定义

```
# My Custom Skill

## 简介
帮我管理待办事项

## Tools
- create_todo: 创建待办
- list_todos: 列出待办
- complete_todo: 完成待办
```

## 3. 实现代码

```
// index.ts
export class MyTodoSkill {
  readonly name = 'my-todo';
  readonly description = '管理待办事项';
  readonly version = '1.0.0';

  private storage: Storage;

  constructor(config: any, context: SkillContext) {
    this.storage = context.storage;
  }

  registerTools() {
    return [
      {
        name: 'create_todo',
        description: '创建一个待办事项',
        parameters: {
          type: 'object',
          properties: {
            title: { type: 'string', description: '待办标题' },
            due: { type: 'string', description: '截止日期' }
          },
          required: ['title']
        }
      },
      {
        name: 'list_todos',
        description: '列出所有待办',
        parameters: { type: 'object', properties: {} }
      }
    ];
  }

  async createTodo(args: { title: string; due?: string }) {
    const todo = {
      id: crypto.randomUUID(),
      title: args.title,
      due: args.due,
      completed: false,
      createdAt: Date.now()
    };
    await this.storage.set(`todo:${todo.id}`, todo);
    return todo;
  }

  async listTodos() {
    const keys = await this.storage.keys('todo:*');
    const todos = await Promise.all(
      keys.map(k => this.storage.get(k))
    );
    return todos;
  }
}
```

---

# 配置示例

```
skills:
  # 官方 Skills
  weather:
    enabled: true
    options:
      api_key: ${WEATHER_API_KEY}
      default_city: 北京

  cron:
    enabled: true

  # 自定义 Skills
  my-todo:
    enabled: true
    path: ./skills/my-todo
```

---

# Agent 如何调用 Skills

```
// Agent 内部逻辑
class Agent {
  private tools = new Map<string, Tool>();

  // LLM 返回 function_call
  async completeWithFunctions(prompt: Prompt, tools: Tool[]): Promise<Response> {
    // 1. 注册 tools
    for (const tool of tools) {
      this.tools.set(tool.name, tool);
    }

    // 2. 调用 LLM
    const response = await this.llm.completeWithTools(prompt, tools);

    // 3. 如果有 function_call
    if (response.function_call) {
      const { name, arguments: args } = response.function_call;

      // 4. 调用 tool
      const result = await this.skillManager.callTool(name, JSON.parse(args));

      // 5. 返回结果给 LLM 生成最终回复
      return await this.llm.complete({
        ...prompt,
        messages: [
          ...prompt.messages,
          response,
          { role: 'function', name, content: JSON.stringify(result) }
        ]
      });
    }

    return response;
  }
}
```

---

# 总结

Skills 系统核心思想：

- **插件化** - 每个 Skill 独立，按需加载

- **工具注册** - 通过 Tool 定义让 LLM 知道能做什么

- **动态调用** - Agent 根据 LLM 的 function_call 动态调用

- **社区生态** - 官方 + 社区 Skills 丰富生态

这就是 OpenClaw "上知天文，下知地理"的秘诀。

---

*下篇预告：《Memory 记忆系统》，详解短期/长期/文件记忆。*
