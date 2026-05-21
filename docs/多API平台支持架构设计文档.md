# 多 API 平台支持架构设计文档

## 📋 目录

1. [当前架构分析](#1-当前架构分析)
2. [最优方案：数据标准化](#2-最优方案数据标准化)
3. [核心模块设计](#3-核心模块设计)
4. [数据流转设计](#4-数据流转设计)
5. [可能踩到的坑](#5-可能踩到的坑)
6. [实施建议](#6-实施建议)

---

## 1. 当前架构分析

### 1.1 技术栈

- **UI 框架**：PyQt5 + QWebEngineView（HTML/CSS 渲染）
- **通信机制**：JavaScript ↔ Python 通过 `console.log` 桥接
- **数据模型**：`UsageSnapshot` + `ModelUsage`
- **配置存储**：JSON 文件（跨平台 APPDATA）

### 1.2 当前数据结构

**HTML 模板期望的字段**（`html_template.py`）：

```javascript
{
  total_balance: float,           // 余额
  topped_up_balance_fmt: string,  // 赠送余额格式化文本
  total_cost: float,              // 费用
  total_tokens_fmt: string,       // Token 格式化文本
  ts_text: string,                // 时间戳文本
  dot_class: string,              // 状态点类名
  model_cards_html: string,       // 模型卡片 HTML
}
```

**当前 UsageSnapshot 字段**（`usage_snapshot.py`）：

```python
{
  fetched_at: datetime,
  total_balance: float,
  granted_balance: float,
  topped_up_balance: float,
  is_available: bool,
  prompt_tokens: int,
  completion_tokens: int,
  total_tokens: int,
  total_cost: float,
  models: list[ModelUsage],
}
```

### 1.3 现有问题

1. **字段假设**：HTML 假设所有平台都有相同字段
2. **数据来源单一**：硬编码 DeepSeek API，难以扩展
3. **UI 紧耦合**：缺少平台适配层，无法处理字段差异

---

## 2. 最优方案：数据标准化

### 2.1 设计原则

**核心思想**：**数据标准化 + 独立适配层**

- 所有 API 平台在返回数据前，先转换为**统一格式**
- HTML 模板只依赖标准格式，无需关心底层 API 差异
- 各平台的转换逻辑独立封装，互不干扰

### 2.2 统一数据结构设计

#### 2.2.1 核心字段定义

**标准 UsageSnapshot**（新增字段）：

```
@dataclass
class UsageSnapshot:
    // === 货币信息（新增）===
    currency: str = "¥"              // 显示货币符号（¥, $, €, etc.）
    currency_symbol: str = "¥"       // API 平台自己的货币符号

    // === 余额（统一格式）===
    total_balance: float = 0.0       // 总余额
    granted_balance: float = 0.0     // 赠送余额
    topped_up_balance: float = 0.0   // 充值余额

    // === 费用 ===
    total_cost: float = 0.0

    // === Token 统计 ===
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    // === 模型列表 ===
    models: list[ModelUsage] = []

    // === 元数据（新增）===
    platform_name: str = "unknown"   // API 平台名称
    last_updated: datetime           // 最后更新时间
    available: bool = False          // 是否有有效数据
    error_msg: str = ""              // 错误信息（如果有）
```

**ModelUsage 扩展**：

```
@dataclass
class ModelUsage:
    model_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    api_calls: int = 0
    cost: float = 0.0
    // 新增字段（可选）
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
```

#### 2.2.2 字段映射规则

| 字段               | DeepSeek   | OpenAI     | Claude     | 处理方式           |
| ------------------ | ---------- | ---------- | ---------- | ------------------ |
| `total_balance`    | ✅ 有      | ❌ 无      | ❌ 无      | 缺失时 = 0.0      |
| `granted_balance`  | ✅ 有      | ❌ 无      | ❌ 无      | 缺失时 = 0.0      |
| `topped_up_balance`| ✅ 有      | ❌ 无      | ❌ 无      | 缺失时 = 0.0      |
| `total_cost`       | ✅ 有      | ✅ 有      | ❌ 无      | 缺失时 = 0.0      |
| `currency`         | ¥          | $          | $          | API 平台自己的货币  |
| `currency_symbol`  | ¥          | $          | $          | API 平台自己的货币  |

### 2.3 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│  展示层 (HTML/CSS)                                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  假设所有字段都存在，无需 if/else 判断                   │  │
│  │  - 直接访问 data.total_balance                         │  │
│  │  - 直接访问 data.total_cost                            │  │
│  │  - 直接访问 data.currency                              │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  API 适配层 (BaseAPI)                                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  abstract BaseAPI:                                     │  │
│  │    - name: str                                        │  │
│  │    - display_name: str                                │  │
│  │    - fetch_snapshot(api_key) -> UsageSnapshot          │  │
│  │    - test_connection(api_key) -> (bool, str)          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  平台实现层 (各 API 平台)                                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  DeepSeekAPI:                                         │  │
│  │    1. 调用 DeepSeek API                                │  │
│  │    2. 数据清洗 + 格式转换                              │  │
│  │    3. 填充缺失字段为 0.0                                │  │
│  │    4. 返回标准 UsageSnapshot                           │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  OpenAIAPI:                                           │  │
│  │    1. 调用 OpenAI API                                 │  │
│  │    2. 数据清洗 + 格式转换                              │  │
│  │    3. 填充缺失余额字段为 0.0                            │  │
│  │    4. 返回标准 UsageSnapshot                           │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  AnthropicAPI:                                        │  │
│  │    1. 调用 Claude API                                 │  │
│  │    2. 数据清洗 + 格式转换                              │  │
│  │    3. 填充缺失费用字段为 0.0                            │  │
│  │    4. 返回标准 UsageSnapshot                           │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  原始 API 层                                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  - DeepSeek API endpoints                              │  │
│  │  - OpenAI API endpoints                                │  │
│  │  - Anthropic API endpoints                             │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 核心模块设计

### 3.1 API 工厂模块

**职责**：

- 动态发现 `src/api/` 目录下的所有平台模块
- 根据配置选择当前平台
- 返回对应的 API 实例

**关键功能**：

```
class APIFactory:
    // 1. 启动时加载所有平台
    _load_platforms() -> list[str]

    // 2. 根据名称创建实例
    create(platform_name) -> BaseAPI

    // 3. 获取平台列表
    list_platforms() -> list[str]

    // 4. 获取平台信息
    get_platform_info(name) -> dict
```

**关键设计点**：

- 使用 Python 的 `importlib` 动态加载模块
- 通过 `_platform_class` 变量约定，无需配置文件
- 自动发现机制，新增平台只需创建文件

### 3.2 BaseAPI 抽象基类

**职责**：

- 定义所有平台必须实现的接口
- 提供默认实现（可选）

**关键方法**：

```
class BaseAPI:
    // 平台标识
    @property
    def name(self) -> str:
        // API 平台标识（如 "deepseek", "openai"）
        pass

    @property
    def display_name(self) -> str:
        // 显示名称（如 "DeepSeek", "OpenAI"）
        pass

    @property
    def description(self) -> str:
        // 平台描述
        pass

    @property
    def currency_symbol(self) -> str:
        // API 平台的货币符号（¥, $, €, etc.）
        pass

    // 核心方法（必须实现）
    def fetch_snapshot(self, api_key: str) -> UsageSnapshot:
        // 获取用量快照
        pass

    def test_connection(self, api_key: str) -> tuple[bool, str]:
        // 测试连接，返回 (成功, 消息)
        pass
```

**设计考虑**：

- 所有字段都是属性，方便扩展
- 核心方法只定义接口，让各平台自己实现
- `currency_symbol` 集中管理货币符号

### 3.3 配置管理扩展

**新增配置项**：

```json
{
  "version": 1,
  "general": {
    "current_api": "deepseek"
  },
  "api_keys": {
    "deepseek": "sk-xxx...",
    "openai": "sk-yyy...",
    "claude": "sk-zzz..."
  }
}
```

**关键方法**：

```
class ConfigManager:
    // 获取当前平台
    get_current_api() -> str

    // 设置当前平台
    set_current_api(api: str)

    // 获取平台 Key
    get_api_key(api_name: str) -> str

    // 设置平台 Key
    set_api_key(api: str, key: str)

    // 获取所有平台 Keys
    get_all_api_keys() -> dict
```

**设计考虑**：

- 每个 API 独立存储 Key，避免混淆
- `current_api` 指示当前使用哪个 API
- 切换 API 时自动读取对应 Key

### 3.4 FetchWorker 改造

**职责**：

- 从配置读取当前 API
- 创建 API 实例
- 调用 `fetch_snapshot()`

**关键流程**：

```
1. 读取 current_api 配置
2. 读取 api_keys[current_api] 配置
3. 调用 APIFactory.create(current_api)
4. 调用 api.fetch_snapshot(api_key)
5. 返回 UsageSnapshot
```

**设计考虑**：

- 无需修改 FetchWorker 代码，只需替换内部实现
- 通过工厂模式解耦，易于测试

### 3.5 设置界面改造

**新增组件**：

#### 3.5.1 平台选择器

```
QComboBox {
  items: ["DeepSeek", "OpenAI", "Claude", ...]
  value: 当前平台显示名称
  signal: currentTextChanged
}
```

#### 3.5.2 API Key 输入框

```
QLineEdit {
  placeholder: "输入 OpenAI 的 API Key..."
  signal: textChanged
}
```

#### 3.5.3 测试连接按钮

```
QPushButton {
  signal: clicked
  action: 测试连接并显示结果
}
```

**交互流程**：

```
1. 用户选择平台 → 更新 placeholder 文本
2. 用户输入 API Key → 自动保存（可选）
3. 用户点击"测试连接" → 调用 API.test_connection()
4. 用户保存 → 更新 current_api + api_keys 配置
```

**设计考虑**：

- 平台选择器和 Key 输入框联动
- 测试连接立即验证 Key 有效性
- 保存后立即生效（下次刷新使用新 API）

---

## 4. 数据流转设计

### 4.1 完整数据流

```
用户操作 → 设置界面 → 配置更新
    ↓
ConfigManager 保存配置
    ↓
下次数据刷新（QTimer 触发）
    ↓
FetchWorker.fetch()
    ↓
读取 current_api + api_key
    ↓
APIFactory.create(current_api)
    ↓
调用 fetch_snapshot(api_key)
    ↓
[各平台实现层]
    ↓
调用原始 API
    ↓
数据清洗 + 格式转换
    ↓
填充缺失字段为 0.0
    ↓
返回标准 UsageSnapshot
    ↓
返回 JSON (to_dict())
    ↓
传给 HTML 模板
    ↓
显示更新
```

### 4.2 平台切换流程

```
场景：用户想从 DeepSeek 切换到 OpenAI

1. 用户打开设置
   ├─ 平台选择器显示：[DeepSeek ▼]
   └─ API Key 输入框显示：sk-deepseek-xxx...

2. 用户选择 "OpenAI"
   ├─ 平台选择器显示：[OpenAI ▼]
   └─ API Key 输入框清空：输入 OpenAI 的 API Key...

3. 用户输入 OpenAI Key
   └─ 自动保存（可选：实时保存）

4. 用户点击"测试连接"
   ├─ 调用 OpenAI.test_connection(key)
   ├─ 返回 (True, "连接成功！余额: $2.50")
   └─ 显示成功消息

5. 用户点击"保存"
   ├─ ConfigManager.set_current_api("openai")
   ├─ ConfigManager.set_api_key("openai", key)
   └─ 保存到 config.json

6. 用户返回主界面
   ↓
   下次数据刷新
   ↓
   FetchWorker 读取 current_api = "openai"
   ↓
   APIFactory.create("openai")
   ↓
   调用 OpenAIAPI.fetch_snapshot(key)
   ↓
   显示 OpenAI 的余额和用量数据
   ✓ 无需重启，立即生效
```

### 4.3 新增平台流程

```
场景：用户想添加 "Xiaohongshu Cloud"

1. 用户创建文件：src/api/xiaohongshu_api.py
   ├─ 定义 XiaohongshuCloudAPI 类
   ├─ 实现 BaseAPI 接口
   └─ 定义 _platform_class = XiaohongshuCloudAPI

2. 无需修改任何其他代码
   ✓ APIFactory 自动发现
   ✓ 设置界面自动显示
   ✓ 用户即可选择使用

3. 用户在设置中配置
   ├─ 选择 "小红书云平台"
   ├─ 输入 API Key
   └─ 测试连接

4. 保存配置
   ├─ current_api = "xiaohongshu"
   └─ api_keys.xiaohongshu = key
```

---

## 5. 可能踩到的坑

### 5.1 数据字段映射坑

#### 坑 1：字段缺失导致的显示问题

**问题描述**：OpenAI 没有"余额"字段，直接映射到 HTML 模板会导致空白。

**风险等级**：🔴 高

**解决方式**：

```
// ❌ 错误方式（直接映射）
def fetch_snapshot(self, api_key):
    raw = _get(api_key, "/usage")
    return UsageSnapshot(
        total_balance=raw["balance"],  // OpenAI 没有 balance 字段 → KeyError
        total_cost=raw["cost"],
    )

// ✅ 正确方式（默认值处理）
def fetch_snapshot(self, api_key):
    raw = _get(api_key, "/usage")
    return UsageSnapshot(
        total_balance=raw.get("balance", 0.0),  // 缺失时 = 0.0
        total_cost=raw.get("cost", 0.0),
    )
```

**预防措施**：

- 所有字段都使用 `.get(key, default)` 而非 `key`
- 统一测试所有平台的缺失字段情况

---

#### 坑 2：货币符号混乱

**问题描述**：不同平台货币符号不同（¥, $, €），直接显示可能导致显示错误。

**风险等级**：🟡 中

**解决方式**：

```
// ❌ 错误方式（硬编码 ¥）
return UsageSnapshot(
    total_balance=balance,
    currency="¥",  // OpenAI 的余额是美元，却显示 ¥
)

// ✅ 正确方式（使用平台自己的货币）
return UsageSnapshot(
    total_balance=balance,
    currency="$",  // 显示美元
    currency_symbol="$",  // OpenAI 的 API 使用 $
)
```

**HTML 显示**：

```javascript
// HTML 自动使用 currency 字段
document.getElementById('bal-val').textContent = data.currency + data.total_balance.toFixed(2);
// 显示：$2.50
```

---

#### 坑 3：费用计算方式不同

**问题描述**：OpenAI 的费用是按输入/输出分别计算，DeepSeek 是总费用。

**风险等级**：🟡 中

**解决方式**：

```
def fetch_snapshot(self, api_key):
    raw = _get(api_key, "/usage")

    // OpenAI: total_cost 是总费用
    return UsageSnapshot(
        total_cost=raw["total_cost"],  // 假设 API 已返回总费用
    )
```

**注意**：

- 需要确认各 API 的费用计算方式
- 如果 API 不返回总费用，需要手动计算

---

### 5.2 API 调用坑

#### 坑 4：认证方式不同

**问题描述**：不同平台的 API Key 格式和验证方式不同。

**风险等级**：🔴 高

**可能情况**：

- DeepSeek: `Bearer sk-xxx...`
- OpenAI: `Bearer sk-xxx...`
- Claude: `sk-ant-xxx...`（不带 Bearer）

**解决方式**：

```
def fetch_snapshot(self, api_key):
    // 根据 platform_name 选择认证方式
    if self.name == "claude":
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
        }

    resp = requests.get(url, headers=headers)
```

---

#### 坑 5：Rate Limit 和重试

**问题描述**：API 调用失败时，需要重试机制。

**风险等级**：🟡 中

**可能情况**：

- 429 Too Many Requests
- 500 Server Error
- 网络超时

**解决方式**：

```
def fetch_snapshot(self, api_key, max_retries=3):
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                return parse_response(resp.json())
            elif resp.status_code == 429:
                time.sleep(2 ** attempt)  // 指数退避
            else:
                raise APIError(f"Status {resp.status_code}")
        except requests.Timeout:
            if attempt == max_retries - 1:
                raise APIError("Request timeout")
            time.sleep(1)
```

---

#### 坑 6：本地缓存数据格式不一致

**问题描述**：首次加载使用缓存数据，但缓存数据可能是旧格式的。

**风险等级**：🟢 低

**解决方式**：

```
// 加载缓存时，自动填充缺失字段
@classmethod
def from_dict(cls, d: dict) -> "UsageSnapshot":
    // 使用 .get() 避免 KeyError
    return cls(
        total_balance=d.get("total_balance", 0.0),
        total_cost=d.get("total_cost", 0.0),
        // ...
    )
```

---

### 5.3 UI 适配坑

#### 坑 7：HTML 模板字段假设

**问题描述**：HTML 模板假设所有字段都存在，导致字段缺失时页面空白。

**风险等级**：🟡 中

**解决方式**：

```javascript
// ❌ 错误方式（假设字段存在）
document.getElementById('bal-val').textContent = data.total_balance;

// ✅ 正确方式（字段存在时显示，不存在时显示 "-"）
var bal_text = data.total_balance > 0 
  ? data.currency + data.total_balance.toFixed(2) 
  : data.available ? "-" : "未配置";

document.getElementById('bal-val').textContent = bal_text;
```

**更好的方式**：

- 使用数据标准化方案（所有字段都存在，但某些字段为 0.0）

---

#### 坑 8：货币符号显示

**问题描述**：不同平台的货币符号不同，直接硬编码在 HTML 中。

**风险等级**：🟢 低

**解决方式**：

```javascript
// ❌ 错误方式（硬编码 ¥）
document.getElementById('bal-val').textContent = '¥' + data.total_balance;

// ✅ 正确方式（使用 data.currency）
document.getElementById('bal-val').textContent = data.currency + data.total_balance;
```

---

#### 坑 9：时间戳格式

**问题描述**：不同平台的返回时间格式不同。

**风险等级**：🟢 低

**解决方式**：

```
def fetch_snapshot(self, api_key):
    raw = _get(api_key, "/usage")
    // 使用 API 返回的时间或当前时间
    timestamp = raw.get("timestamp", datetime.datetime.now())
    return UsageSnapshot(
        last_updated=timestamp,
    )
```

---

### 5.4 配置管理坑

#### 坑 10：API Key 混淆

**问题描述**：多个 API 的 Key 混在一起，容易输错。

**风险等级**：🟡 中

**解决方式**：

- 设置界面按平台分类显示 Key 输入框
- 平台选择器和 Key 输入框联动
- 测试连接验证 Key 有效性

**UI 设计**：

```
┌─────────────────────────────────┐
│ 选择 API 平台: [DeepSeek ▼]      │
├─────────────────────────────────┤
│ DeepSeek API Key: sk-xxx...     │
└─────────────────────────────────┘

点击 "选择 OpenAI" 后：
┌─────────────────────────────────┐
│ 选择 API 平台: [OpenAI ▼]       │
├─────────────────────────────────┤
│ OpenAI API Key: sk-yyy...       │
└─────────────────────────────────┘
```

---

#### 坑 11：配置迁移问题

**问题描述**：从单 API 平台迁移到多 API 平台时，旧配置文件不兼容。

**风险等级**：🟡 中

**解决方式**：

```
def load(self):
    // 1. 加载配置
    data = json.load(...)

    // 2. 检查是否是旧格式（没有 api_keys 字段）
    if "api_keys" not in data:
        // 迁移旧配置
        old_key = data.get("api", {}).get("api_key")
        data["api_keys"] = {
            "deepseek": old_key,
        }

    // 3. 确保 api_keys 字段存在
    if "api_keys" not in data:
        data["api_keys"] = {}

    // 4. 检查 current_api 是否存在
    if "current_api" not in data.get("general", {}):
        data["general"]["current_api"] = "deepseek"

    return data
```

---

#### 坑 12：配置文件损坏

**问题描述**：用户手动编辑 config.json，导致格式错误。

**风险等级**：🟢 低

**解决方式**：

```
def load(self):
    try:
        with open(path, "r", encoding="utf-8") as f:
            self._data = json.load(f)
    except json.JSONDecodeError:
        // 恢复默认配置
        self._data = DEFAULT_CONFIG.copy()
        self.save()
```

---

### 5.5 线程安全坑

#### 坑 13：多线程配置读取

**问题描述**：配置在多个线程中同时读取和修改。

**风险等级**：🟡 中

**解决方式**：

```
import threading

class ConfigManager:
    _lock = threading.Lock()

    def get_current_api(self) -> str:
        with self._lock:
            return self._data.get("general", {}).get("current_api", "deepseek")

    def set_current_api(self, api: str):
        with self._lock:
            self._data.setdefault("general", {})["current_api"] = api
            self.save()
```

---

#### 坑 14：API 实例缓存

**问题描述**：每次刷新都创建新的 API 实例，可能导致状态丢失。

**风险等级**：🟢 低

**解决方式**：

```
class FetchWorker(QObject):
    def __init__(self):
        self._api_instance = None

    def fetch(self):
        // 缓存 API 实例
        if self._api_instance is None:
            self._api_instance = APIFactory.create(current_api)

        snapshot = self._api_instance.fetch_snapshot(api_key)
```

---

## 6. 实施建议

### 6.1 分阶段实施

#### 阶段 1：基础架构（1-2 天）

1. 创建 `src/api/base.py` - 定义 BaseAPI 接口
2. 创建 `src/api/factory.py` - 实现 API 工厂
3. 扩展 `config_manager.py` - 添加 API 配置字段
4. 改造 `fetch_worker.py` - 使用 API 工厂

**验收标准**：

- ✅ 能切换不同 API 平台
- ✅ 配置正确保存和加载

---

#### 阶段 2：DeepSeek 适配（1 天）

1. 将 `deepseek_api.py` 改造为 `api/deepseek.py`
2. 实现 BaseAPI 接口
3. 数据格式转换
4. 测试功能

**验收标准**：

- ✅ DeepSeek 功能不变
- ✅ 数据格式标准化

---

#### 阶段 3：OpenAI 适配（1-2 天）

1. 创建 `api/openai.py`
2. 实现 OpenAI API 调用
3. 数据格式转换
4. 测试连接功能

**验收标准**：

- ✅ 能正常获取 OpenAI 数据
- ✅ 余额缺失时显示 "-"

---

#### 阶段 4：Claude 适配（1-2 天）

1. 创建 `api/anthropic.py`
2. 实现 Claude API 调用
3. 数据格式转换
4. 测试连接功能

**验收标准**：

- ✅ 能正常获取 Claude 数据
- ✅ 费用缺失时显示 "-"

---

#### 阶段 5：设置界面改造（1 天）

1. 添加平台选择器
2. 添加 API Key 输入框
3. 添加测试连接按钮
4. 实现平台切换逻辑

**验收标准**：

- ✅ 能切换平台
- ✅ Key 输入正确保存
- ✅ 测试连接可用

---

#### 阶段 6：单元测试（1 天）

1. 测试各平台数据转换
2. 测试字段缺失情况
3. 测试 API 切换功能
4. 测试并发读取配置

**验收标准**：

- ✅ 所有平台都能正常工作
- ✅ 字段缺失时显示正确

---

### 6.2 测试清单

**功能测试**：

- [ ] 切换 DeepSeek → OpenAI
- [ ] 切换 OpenAI → Claude
- [ ] 测试连接 DeepSeek API
- [ ] 测试连接 OpenAI API
- [ ] 测试连接 Claude API
- [ ] 余额缺失时显示 "-"
- [ ] 货币符号正确显示

**边界测试**：

- [ ] 空的 API Key
- [ ] 无效的 API Key
- [ ] 网络超时
- [ ] API 调用失败
- [ ] 配置文件损坏

**并发测试**：

- [ ] 同时刷新多个平台
- [ ] 快速切换平台
- [ ] 保存配置时正在刷新

---

### 6.3 性能优化建议

1. **API 调用优化**：
   - 使用连接池（`requests.Session`）
   - 实现请求缓存
   - 并行请求多个端点

2. **数据转换优化**：
   - 缓存常用字段
   - 避免重复计算
   - 使用数据类减少内存占用

3. **UI 优化**：
   - 使用虚拟滚动（模型列表很长时）
   - 延迟加载图片
   - 减少不必要的重绘

---

### 6.4 安全建议

1. **API Key 安全**：
   - 不在日志中输出完整 Key
   - 清空输入框时可选加密
   - 建议使用环境变量

2. **HTTPS 加密**：
   - 所有 API 调用使用 HTTPS
   - 验证 SSL 证书

3. **权限控制**：
   - 不记录用户的 Key
   - 不上传任何数据到服务器

---

### 6.5 扩展性建议

1. **插件化架构**：
   - 支持用户自定义 API 平台
   - 允许用户编写 Python 插件

2. **统一协议**：
   - 设计统一的 API 协议
   - 支持未来更多平台

3. **配置热加载**：
   - 配置修改后无需重启
   - 动态加载新平台模块

---

## 总结

### 核心优势

1. **稳定性**：数据标准化确保界面一致
2. **可维护性**：各平台独立，互不干扰
3. **扩展性**：新增平台无需修改代码
4. **用户体验**：切换 API 无需重启

### 风险控制

1. 字段缺失时使用默认值
2. 货币符号动态管理
3. 认证方式适配
4. 配置迁移兼容

### 实施路线

1. 基础架构 → DeepSeek 适配 → OpenAI 适配
2. Claude 适配 → 设置界面 → 单元测试
3. 总计：5-7 天完成

---

**文档版本**：v1.0  
**更新日期**：2026-05-09  
**适用项目**：float - 多 API 平台支持重构
