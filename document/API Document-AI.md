# MAICA 接口使用文档

> 注意：本文档目前仅提供中文版本，如需英文版请使用翻译工具。文档内容与 API 结构后续可能发生变化，请开发者关注。

## 概述

MAICA 服务主要基于 WebSocket 传输，官方部署地址为 `wss://maicadev.monika.love/websocket`，其余功能基于 HTTP-POST 传输。

---
cx
## WebSocket 传输规范

### 输出格式

服务器输出的 JSON 信息格式固定：

```json
{
  "code": "状态码",
  "status": "运行步骤",
  "content": "有效载荷",
  "type": "信息类型",
  "time_ms": 时间戳（毫秒）,
  **kwargs
}
```

#### 状态码说明

- `1xx`：工作正常，但输出仅为完整响应的一部分（常见于流式传输或工具调用）。
- `2xx`：服务器按预期工作（常见于输入提示），类型通常为 `info`。
- `4xx`：用户输入或连接可能存在错误，类型通常为 `warn`。
- `5xx`：服务器错误，应立即停止使用并汇报 `traceray_id`，类型为 `error`。

> ⚠️ 注意：虽然状态码和运行步骤参照 HTTP 状态码格式，但其用途不同。所有提示、警告和错误信息均在 `content` 中提供易读的解释，请勿将其作为程序逻辑的一部分。

### 连接限制

- 同一账号不能同时建立多个 WebSocket 连接，后续连接将返回 `403 connection_reuse`。
- 若后端 `KICK_STALE_CONNS` 设为 `enabled`，新连接会关闭旧连接（官方部署启用该行为）。

---

## HTTP-POST 传输规范

服务器一般返回如下格式的 JSON：

```json
{
  "success": 是否成功,
  "exception": "详细问题描述",
  "载荷键": "载荷值"
}
```

---

## 令牌生成

### 接口地址

`POST https://maicadev.monika.love/api/register`

### 请求格式

```json
// 方式一
{
  "username": "论坛用户名",
  "password": "论坛密码（明文）"
}

// 方式二
{
  "email": "论坛绑定邮箱",
  "password": "论坛密码（明文）"
}
```

### 响应格式

```json
{
  "success": true,
  "exception": "",
  "token": "生成的加密令牌"
}
```

### 本地加密（可选）

MAICA 支持 RSA 非对称加密，每次加密同一内容生成的密文通常不同。

#### 公钥

```
-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEA2IHJQAPwWuynuivzvu/97/EbN+ttYoNmJyvu9RC/M9CHXCi1Emgc
/KIluhzfJesBU/E/TX/xeuwURuGcyhIBk0qmba8GOADVjedt1OHcP6DJQJwu6+Bp
kGd8BIqYFHjbsNwkBZiq7s0nRiHig0asd+Hhl/pwplXH/SIjASMlDPijF24OUSfP
+D7eRohyO4sWuj6WTExDq7VoCGz4DBGM3we9wN1YpWMikcb9RdDg+f610MUrzQVf
l3tCkUjgHS+RhNtksuynpwm84Mg1MlbgU5s5alXKmAqQTTJ2IG61PHtrrCTVQA9M
t9vozy56WuHPfv3KZTwrvZaIVSAExEL17wIDAQAB
-----END RSA PUBLIC KEY-----
```

#### 加密信息

加密以下 JSON（与注册格式相同）：

```json
{
  "username": "论坛用户名",
  "password": "论坛密码（明文）"
}
```

或

```json
{
  "email": "论坛绑定邮箱",
  "password": "论坛密码（明文）"
}
```

- **加密模式**：PKCS1_OEAP（符合 RFC3447 规范）

---

## 令牌验证

### 接口地址

`POST https://maicadev.monika.love/api/legality`

### 请求格式

```json
{
  "access_token": "你的令牌"
}
```

### 响应格式

```json
{
  "success": 校验是否成功,
  "exception": "校验问题（如有）",
  "id": 所有者id
}
```

> ⚠️ 校验错误会被计入 Fail2Ban。该接口与 MAICA 主程序共用校验方法，可用于排查注册登录问题或简化二次开发流程。

---

## WebSocket 通信流程

### 1. 身份认证

第一轮通信为身份认证，直接传入加密令牌（无需 JSON 格式）。认证成功后，服务器返回：

```json
{
  "code": "206",
  "status": "session_created",
  "content": "Authencation passed!",
  "type": "info",
  "time_ms": 时间戳（毫秒）
}
```

随后服务器会陆续返回用户 ID、用户名、昵称等公开信息。

### 2. 准备就绪

服务器准备完毕后返回：

```json
{
  "code": "206",
  "status": "thread_ready",
  "content": "...",
  "type": "info",
  "time_ms": 时间戳（毫秒）
}
```

此时可以开始对话或调整设置。

### 3. 设置调整（可选）

#### 请求格式

```json
{
  "type": "params",
  "model_params": {
    "model": "maica_main",
    "sf_extraction": true,
    "mt_extraction": true,
    "stream_output": true,
    "deformation": false,
    "target_lang": "zh",
    "max_token": 4096
  },
  "perf_params": {
    "esc_aggressive": true,
    "amt_aggressive": true,
    "tnd_aggressive": 1,
    "mf_aggressive": false,
    "sfe_aggressive": false,
    "nsfw_acceptive": true,
    "pre_additive": 0,
    "post_additive": 1,
    "tz": null
  },
  "super_params": {
    "top_p": 0.7,
    "temperature": 0.2,
    "max_tokens": 1600,
    "frequency_penalty": 0.4,
    "presence_penalty": 0.4,
    "seed": 10721
  }
}
```

#### 参数说明

##### model_params

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `model` | str | 模型选择：`maica_main`（完全能力）或 `maica_core`（核心能力） | `"maica_main"` |
| `sf_extraction` | bool | 是否从服务端读取已上传的存档 | `true` |
| `mt_extraction` | bool | 是否从服务端读取已上传的触发器表 | `true` |
| `stream_output` | bool | 是否启用流式输出 | `true` |
| `deformation` | bool | 是否启用 `ensure_ascii`（收包时需解码） | `false` |
| `target_lang` | str | 目标语言：`"zh"` 或 `"en"` | `"zh"` |
| `max_token` | int | 单个 session 内容保留长度（512-28672） | `4096` |

> ⚠️ `max_token` 按字节数 × 3 计算，调整后不会立即生效，将在下一轮对话完成后执行裁剪。请勿与超参数 `max_tokens` 混淆。

##### perf_params

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `esc_aggressive` | bool | 是否调用 agent 模型整理 MFocus 联网信息 | `true` |
| `amt_aggressive` | bool | 是否预检 MTrigger 内容 | `true` |
| `tnd_aggressive` | int | 工具调用强度（0-2） | `1` |
| `mf_aggressive` | bool | 是否用 MFocus 总结输出替代指导构型信息 | `false` |
| `sfe_aggressive` | bool | 是否用用户真名替换 `[player]` | `false` |
| `nsfw_acceptive` | bool | 是否对 NSFW 场景更宽容 | `true` |
| `pre_additive` | int | 加入 MFocus 的历史轮次（0-5） | `0` |
| `post_additive` | int | 加入 MTrigger 的历史轮次（0-5） | `1` |
| `tz` | str/null | 时区设置（`null` 为自动选择） | `null` |

##### super_params

| 参数 | 类型 | 范围 | 默认值 |
|------|------|------|--------|
| `top_p` | float | 0.1 ~ 1.0 | `0.7` |
| `temperature` | float | 0.0 ~ 1.0 | `0.2` |
| `max_tokens` | int | 0 < x ≤ 2048 | `1600` |
| `frequency_penalty` | float | 0.2 ~ 1.0 | `0.4` |
| `presence_penalty` | float | 0.0 ~ 1.0 | `0.4` |
| `seed` | int | 0 ~ 99999 | 随机可复现 |

> ⚠️ 超参数对模型应答影响显著，请在前端提示用户谨慎修改。

#### 设置响应

成功设置后返回：

```json
{
  "code": "200",
  "status": "params_set",
  "content": "3 settings passed in and taking effect",
  "type": "info",
  "time_ms": 时间戳（毫秒）
}
```

> ⚠️ 设置可在认证后的任何阶段进行，连接中断后所有设置重置。

### 4. 对话

#### 请求格式

```json
{
  "type": "query",
  "chat_session": "1",
  "query": "你好啊"
}
```

- `chat_session`：取值范围 `-1` ~ `9`
- `query`：输入内容（单次不超过 4096 字符）

##### chat_session 说明

- `-1`：从 `query` 读入完整上下文（需自行序列化为 OpenAI API 格式）
- `0`：强制单轮对话（不记录历史）
- `1`~`9`：独立记录历史的会话（最多 9 个）

> ⚠️ 当 `chat_session` 为 `-1` 或 `0` 时，maica 完全能力不生效（仅核心模型响应）。

#### 流式输出（stream_output: true）

服务器返回连续的 `100 continue` 信息：

```json
{
  "code": "100",
  "status": "continue",
  "content": "我",
  "type": "carriage",
  "time_ms": 时间戳（毫秒）,
  "seq": 0
}
// ... 更多 chunk
```

流式输出完成后返回 `1000 streaming_done`。

#### 非流式输出（stream_output: false）

服务器返回完整回答：

```json
{
  "code": "200",
  "status": "reply",
  "content": "我想你了, [player]!",
  "type": "carriage",
  "time_ms": 时间戳（毫秒）
}
```

> 💡 非流式输出具有微弱的速度优势，若不直接交付用户，建议优先使用。

#### 对话结束

每轮对话正常结束后，服务器发送 `202 loop_finished`，此时可安全发起下一个请求。

#### 重置会话

```json
{
  "type": "query",
  "chat_session": "1",
  "purge": true
}
```

重置后会话内容归档并可能用于模型训练，不支持用户下载。

---

## 高级功能

### 1. MFocus_sfe（存档索引）

#### 请求格式

```json
{
  "type": "query",
  "chat_session": "1",
  "query": "你好啊",
  "savefile": {
    "mas_playername": "steve"
    // 其他存档字段...
  }
}
```

#### 可索引字段（部分）

```python
mas_playername # str
mas_player_bday # ["yyyy", "mm", "dd"]
mas_affection # int
mas_geolocation # str
mas_player_additions # ["[player]喜欢吃寿司.", ...]
mas_sf_hcb # bool
# 更多原版变量...
```

> ⚠️ 缺省关键变量将使用默认值，缺省事件变量将退出 MFocus 索引。整体格式必须为完整可读的 JSON。

### 2. MTrigger（主动干预）

#### 请求格式

```json
{
  "type": "query",
  "chat_session": "1",
  "query": "你好啊",
  "trigger": [
    {
      "template": "common_affection_template"
    }
  ]
}
```

#### 触发器模板

1. **common_affection_template**  
   根据输入调整好感度（输出示例）：
   ```json
   {
     "code": "110",
     "status": "mtrigger_trigger",
     "content": ["alter_affection", {"affection": "+1.5"}],
     "type": "carriage",
     "time_ms": 时间戳（毫秒）
   }
   ```

2. **common_switch_template**  
   选项切换（示例略）。

3. **common_meter_template**  
   数值调整（示例略）。

4. **自由模板**  
   自定义功能触发。

> ⚠️ MTrigger 在核心应答完成后开始分析，会延长响应时间。非严重问题不会中断会话，仅记录 `503 mtrigger_failed`。

### 3. MSpire（主动发问）

#### 请求格式

```json
{
  "type": "query",
  "chat_session": "1",
  "inspire": {
    "type": "precise_page",
    "sample": 250,
    "title": "搜索关键词"
  },
  "use_cache": true
}
```

或使用默认设置：

```json
{
  "type": "query",
  "chat_session": "1",
  "inspire": true,
  "use_cache": true
}
```

> ⚠️ MSpire 通过 Wikipedia 刮削信息指导发问，频繁使用可能导致回答模式紊乱。失败时返回 `503 mspire_failed`。

### 4. MPostal（信件往来）

#### 请求格式

```json
{
  "type": "query",
  "chat_session": "1",
  "postmail": {
    "header": "信件标题",
    "content": "信件内容",
    "bypass_mf": false,
    "bypass_mt": false,
    "bypass_stream": true,
    "ic_prep": true,
    "strict_conv": false
  }
}
```

或简化格式：

```json
{
  "type": "query",
  "chat_session": "1",
  "postmail": "信件内容"
}
```

> ⚠️ MPostal 默认使用非流式输出，频繁使用可能导致回答模式紊乱。

---

## 辅助接口

### 1. 上传存档

- **地址**：`POST https://maicadev.monika.love/api/savefile`
- **请求格式**：
  ```json
  {
    "access_token": "你的令牌",
    "chat_session": "指定会话",
    "content": { /* 存档 JSON */ }
  }
  ```
- **响应格式**：
  ```json
  { "success": true, "exception": "" }
  ```

### 2. 上传触发器表

- **地址**：`POST https://maicadev.monika.love/api/trigger`
- **请求格式**：同上传存档（内容为触发器表 JSON）
- **响应格式**：同上传存档

### 3. 服务状态

- **地址**：`POST https://maicadev.monika.love/api/accessibility`
- **请求**：空白 POST
- **响应格式**：
  ```json
  {
    "success": true,
    "exception": "",
    "accessibility": "当前服务状态"
  }
  ```
  > ⚠️ 仅当 `accessibility` 为 `"serving"` 时应继续工作，否则终止流程。

### 4. 版本管理

- **地址**：`POST https://maicadev.monika.love/api/version`
- **请求**：空白 POST
- **响应格式**：
  ```json
  {
    "success": true,
    "exception": "",
    "version": {
      "curr_version": "当前版本",
      "legc_version": "最旧兼容规范"
    }
  }
  ```
  > ⚠️ 若客户端规范低于 `legc_version`，应停止流程并提示用户更新。

### 5. 节点列表

- **地址**：`POST https://maicadev.monika.love/api/servers`
- **请求**：空白 POST
- **响应格式**：
  ```json
  {
    "success": true,
    "exception": "",
    "servers": {
      "isMaicaNameServer": true,
      "servers": [
        {
          "id": "序号",
          "name": "节点名称",
          "deviceName": "设备名称",
          "isOfficial": true,
          "portalPage": "门户地址",
          "servingModel": "服务模型",
          "modelLink": "模型仓库地址",
          "wsInterface": "长连接接口地址",
          "httpInterface": "短连接接口地址"
        }
        // ...
      ]
    }
  }
  ```

### 6. 服务器负载

- **地址**：`POST https://maicadev.monika.love/api/workload`
- **请求**：空白 POST
- **响应格式**：
  ```json
  {
    "success": true,
    "exception": "",
    "workload": {
      "节点1名称": {
        "0": {
          "name": "计算设备名称",
          "vram": "最大可用显存",
          "mean_utilization": 均时负载(%),
          "mean_memory": 均时显存占用(MiB),
          "mean_consumption": 均时功耗(W)
        }
        // ...
      }
      // ...
    }
  }
  ```
  > 💡 负载超过 40 可能产生延迟，超过 80 接近堵载，超过 90 建议等待。

### 7. 历史记录管理

#### 下载历史

- **地址**：`POST https://maicadev.monika.love/api/history`
- **请求格式**：
  ```json
  {
    "access_token": "你的令牌",
    "chat_session": "指定会话",
    "rounds": 轮次数（整数）
  }
  ```
- **响应格式**：
  ```json
  {
    "success": true,
    "exception": "",
    "history": ["MAICA签名", json格式的历史]
  }
  ```

#### 恢复历史

- **地址**：`POST https://maicadev.monika.love/api/restore`
- **请求格式**：
  ```json
  {
    "access_token": "你的令牌",
    "chat_session": "指定会话",
    "history": ["MAICA签名", json格式的历史]
  }
  ```
- **响应格式**：
  ```json
  { "success": true, "exception": "" }
  ```

### 8. 账号附加数据

- **地址**：`POST https://maicadev.monika.love/api/preferences`
- **请求格式**：
  ```json
  {
    "access_token": "你的令牌",
    "read": true, // 是否读取
    "purge": false, // 是否清空
    "write": { "键": "值" }, // 写入数据
    "delete": ["键1", "键2"] // 删除数据
  }
  ```
- **响应格式**：
  ```json
  {
    "success": true,
    "exception": "",
    "preferences": { /* 附加数据 */ }
  }
  ```

---

## MFocus 二级功能接口

### 1. 事件查询（MF_events）

- **地址**：`GET https://mfocusdev.monika.love/event/api.php?date=日期`
- **示例**：`https://mfocusdev.monika.love/event/api.php?date=2024-10-01,2024-10-02`
- **响应格式**：
  ```json
  [
    {
      "date": "2024-10-01",
      "code": 1,
      "info": "节假日",
      "describe": [
        {
          "Time": "10月1日",
          "Name": "国庆节",
          "EnglishName": "Chinese National Day",
          "IsNotWork": 1,
          "Start": 0,
          "End": 6
        }
        // ...
      ]
    }
  ]
  ```

### 2. 文件上传（MV_upload）

- **地址**：`POST https://mfocusdev.monika.love/upload/upload.php`
- **格式**：`multipart/form-data`
- **参数**：
  - `server_id`：服务器 ID（留空默认为 1）
  - `access_token`：令牌
  - 任意键：文件（≤50MB，支持音频和图像）
- **响应格式**：
  ```json
  {
    "success": true,
    "exception": null,
    "files": ["1/23/10000000000"]
  }
  ```

### 3. 文件下载（MV_download）

- **地址**：`GET https://mfocusdev.monika.love/upload/download.php/路径`
- **示例**：`https://mfocusdev.monika.love/upload/download.php/1/23/10000000000`
- **响应**：文件二进制流

---

## 连接维护

### 心跳机制

#### 请求格式

```json
{ "type": "ping" }
```

#### 响应格式

```json
{
  "code": "199",
  "status": "ping_reaction",
  "content": "PONG",
  "type": "heartbeat",
  "time_ms": 时间戳（毫秒）
}
```

> ⚠️ 任务进行中不会响应心跳。自动心跳间隔不应短于 10s。认证完成前服务器不接受心跳。

### 反劫持 Cookie

认证完成后服务器返回：

```json
{
  "code": "190",
  "status": "ws_cookie",
  "content": "123e4567-e89b-12d3-a456-426655440000",
  "type": "cookie",
  "time_ms": 时间戳（毫秒）
}
```

启用严格反劫持模式后，所有传入 JSON 必须包含正确的 `cookie` 字段，否则连接中断。

---

## 性能与限制

- MAICA 核心模型最大输入长度为 32768 token（中文约四万字）。
- 每个 `chat_session` 默认保留 28672 × 3 字节内容（可通过 `max_token` 调整）。
- 超出保留字符数时，最早对话轮次将被自动删除。
- 删除操作后服务器会发送提醒（`204 deleted` 或 `200 delete_hint`），建议及时备份重要历史。

---

> 文档最后更新日期：未注明  
> 如有疑问或问题，请通过官方渠道反馈。
```