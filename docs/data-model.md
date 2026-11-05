# 记录模型与关联设计（提案）

- 状态：设计提案，尚未实现
- 最后更新：2026-11-06
- 适用范围：`backend/`、`web/`、AI tool 层、MCP
- 相关规格：`#14` Place、`#15` Trip、`#16` TripItem、`#17` Hotel、`#18` Activity、`#19` Expense、`#21` Note、`#27` Map、`#28` Statistics

> 本文用于指导后续开发。实施前请先确认本文件与产品规格不冲突；如果确认采用，应同步更新规格中关于 TripItem/Place 的旧描述，避免后续开发按旧模型把冗余加回来。

---

## 1. 背景与要解决的问题

当前实现中已经出现三类结构性冗余：

1. **地点与活动重复**
   - `TripItem` 同时支持 `place` 和 `activity`；
   - Activity 可以通过 `place_id` 关联地点；
   - 但两者之间没有去重，行程详情会出现「活动卡片 + 同一地点的地点卡片」。

2. **记录价格与开销重复**
   - TransportRecord、Hotel、Activity 都有 `price/currency`；
   - Expense 又有独立的 `amount/currency`；
   - 两者没有关联，也没有统一统计口径，用户可能对同一笔支出录两遍。

3. **TripItem 保存了一份重复的时间**
   - Transport、Hotel、Activity 本身已有时间；
   - `trip_items.start_at/end_at` 又保存一份；
   - 通过 `PATCH /trips/{id}/items/{item_id}` 还能直接修改这份时间，容易与源记录漂移。

目标不是把所有实体合并成一张表，而是明确每类数据的职责，让**每类事实只有一个权威来源**。

---

## 2. 分层原则

按职责把数据分成五层：

| 层 | 类型 | 职责 | 是否进行程时间线 |
|---|---|---|---:|
| 事件 | TransportRecord | 航班/火车/其他交通 | 是 |
| 事件 | Hotel | 住宿 | 是 |
| 事件 | Activity | 活动/到访 | 是 |
| 引用 | Place | 地点库、地理引用 | 否 |
| 账务 | Expense | 实际花费 | 否 |
| 内容 | Note / Attachment | 笔记、附件 | 否 |
| 容器 | Trip | 一次旅行的聚合 | — |
| 投影 | TripItem | 时间线成员与排序 | — |

核心原则：

- **时间线只放“什么时候发生了什么”**：Transport、Hotel、Activity。
- **Place 是“在哪里”**，不再自己承担行程归属。
- **Expense 是“实际花了多少钱”**，记录上的 price 只是参考价。
- **Note / Attachment 是内容**，在行程详情中独立分区展示。
- **TripItem 只做排序投影**，不复制权威时间，也不决定成员归属。

---

## 3. 目标关系

```text
Trip
├── TransportRecord  0..N
├── Hotel            0..N
├── Activity         0..N
├── Expense          0..N
└── Note             0..N

Place
└── Activity         0..N   （活动/到访发生在某个地点）

Transport / Hotel / Activity
└── Expense          0..N   （实际花费来源，可选）

TripItem
└── 只投影 Transport / Hotel / Activity 的成员与排序
```

说明：

- `trip_id` 是行程归属的唯一事实来源。
- `TripItem` 只是时间线展示层；成员关系仍由源记录的 `trip_id` 决定。
- Place 不保存 `trip_id`。
- Expense、Note、Attachment 不进入 TripItem。
- Hotel 和 Transport 暂不强制关联 Place，原因见第 7 节。

---

## 4. Place 与 Activity

### 4.1 Place 的定位

保留 Place，作为**用户自己维护的地点库**：

- 字段：类型、国家/省/市/区、名称、本地名称、经纬度、时区、外部 ID；
- 不保存行程归属；
- 不直接成为 TripItem；
- 可被 Activity 引用；
- 地点库继续独立存在，提供搜索、筛选、收藏和未来的地图能力。

Place 类型中的 `airport/train_station/...` 仅表示地点分类，不代表交通记录必须引用 Place。

### 4.2 到访通过 Activity 表达

“把地点加入行程”不再创建 `item_type='place'`，而是创建一条 Activity：

```text
Activity
- type = "visit"
- name = 默认取 Place.name，可修改
- place_id = 目标地点
- trip_id = 目标行程
- start_at / end_at = 到访时间，可空
```

因此：

- “我想去滨海湾花园” = 一条 `visit` 活动；
- “我在滨海湾花园看灯光秀” = 一条 `sightseeing` 活动，关联同一个 Place；
- 地点本身仍然在 Place 库中，不重复进入时间线。

`Activity.name` 保持必填。纯到访时默认使用 Place 名称；这是一个**快照**，之后 Place 改名不会自动改 Activity 名称。

### 4.3 允许同一地点多次到访

**不要对 `(trip_id, place_id)` 做唯一约束。**

同一个地点在同一行程中出现多次是合法场景：

- 机场往返各一次；
- 同一家餐厅吃两次；
- 同一景点白天、晚上各去一次；
- 酒店作为地点，关联多个活动。

需要防的是**同一次事件的重复录入**，不是同一地点出现多次。

规则：

- UI 从 Place 详情“加入行程”时，先展示该行程已有的同地点活动；
- 用户明确选择“新建一次到访”才创建新 Activity；
- AI 在创建前先查询 `search_activities(trip_id, place_id)`，避免重复提交同一次事件；
- 只有在地点、时间窗口和事件内容都相同时，才提示疑似重复。

### 4.4 活动卡片显示地点

行程时间线中的 Activity 卡片必须显示地点信息：

```text
灯光秀
观光 · 9月26日 19:00 · 📍 滨海湾花园
```

地点名称链接到 `/places/{id}`，但不单独生成 Place 卡片。

### 4.5 无时间的到访

如果用户只把地点加入行程、还没安排时间：

- 不强行插入按时间排序的时间线；
- 在行程详情显示为“未安排 / 候选地点”；
- 补上时间后进入正式时间线。

这样不需要额外引入 `TripPlace` 表。

---

## 5. TripItem 的职责收缩

### 5.1 只允许三种类型

```text
item_type ∈ { transport, hotel, activity }
```

不再允许 `place`。

### 5.2 时间由源实体提供

`trip_items.start_at/end_at` 不再作为权威数据。

时间来源：

| 类型 | 时间来源 |
|---|---|
| transport | `departure_time` / `arrival_time` |
| hotel | `check_in` / `check_out` |
| activity | `start_at` / `end_at` |

`TripItemRead.start_at/end_at` 可以继续返回给前端，但由源实体实时计算。

`TripItem` 最终只保留：

- `trip_id`
- `item_type`
- `item_id`
- `sort_order`

### 5.3 禁止通过 TripItem 改时间

- `PATCH /trips/{id}/items/{item_id}` 不再允许修改 `start_at/end_at`；
- 改时间必须修改 Transport / Hotel / Activity 本身；
- `TripItem` 只负责 `sort_order`。

迁移完成后，用单独的 Alembic migration 删除 `trip_items.start_at/end_at`。

### 5.4 统一自愈

当前 `list_items()` 只执行 `ensure_transport_items()`。改造后应提供：

```text
ensure_timeline_items()
```

对 transport、hotel、activity 三种类型都补齐缺失的投影行，避免旧数据漏出时间线。

### 5.5 移出行程

TripItem 是投影，不能直接删投影行来表达“移出行程”。

新的语义：

- `DELETE /trips/{id}/items/{item_id}` 表示“把源记录移出该行程”；
- 对 transport/hotel/activity 统一执行：清空源记录的 `trip_id`，再同步删除投影；
- 不删除源记录本身；
- 旧 API 可以保留为门面，避免前端和已有调用直接失效。

---

## 6. Expense 与记录价格

### 6.1 单一实际花费来源

**Expense 是实际花费的唯一权威来源。**

统计、行程总花费、分类汇总，只读 Expense。

TransportRecord、Hotel、Activity 上的 `price/currency` 保留，但明确语义为：

> 票面价 / 预订价 / 参考价，不参与实际花费汇总。

数据库字段暂不改名；先改 UI 文案和统计口径：

- 记录表单：`票价 / 预订价（参考）`
- 开销：`实际支出`

### 6.2 Expense 增加来源关联

新增字段：

```text
source_type: flight | train | other | hotel | activity | null
source_id: UUID | null
```

`source_type` 直接复用现有记录词表，不再引入 `transport/other` 混用的新命名。

允许：

- 一张机票对应多笔开销（票价、行李费、选座费）；
- 一家酒店对应多笔开销（定金、尾款）；
- 一个活动对应多笔开销；
- 完全没有来源的独立开销（餐饮、购物、打车）。

**不强制一对一，也不按金额自动猜来源。**

### 6.3 有来源时行程由来源派生

为了避免出现：

```text
航班属于行程 A
机票开销却属于行程 B
```

规则：

- 有 `source_*` 时，`Expense.trip_id` 从来源记录派生；
- 创建时不允许手工指定与来源冲突的 `trip_id`；
- 来源记录移动行程时，关联 Expense 同步移动；
- 来源记录被移出行程时，关联 Expense 也移出；
- 无来源时，`trip_id` 由用户手工指定。

### 6.4 来源删除

删除来源记录时：

- 保留 Expense；
- 清除 `source_type/source_id`；
- 保留删除前的 `trip_id` 作为历史快照；
- 之后该 Expense 变成普通的手工开销。

### 6.5 不自动把 price 变成 Expense

创建航班、酒店、活动时，**不默认生成开销**。

改为在记录详情页提供显式操作：

```text
[记一笔开销]
```

点击后预填：

- 金额、币种；
- 分类；
- 行程（从来源派生）；
- 来源记录；
- 日期。

并在记录上显示“已记账 N 笔 / 未记账”，让用户知道是否重复。

### 6.6 多币种统计

以 `user.currency` 为报告币种：

1. `expense.currency == user.currency`：使用 `amount`；
2. 否则，如果 `converted_currency == user.currency` 且有 `converted_amount`：使用 `converted_amount`；
3. 否则进入“未换算”分组，不强行加入总额。

页面应显示：

```text
已折算总花费：12,480 CNY
未换算：3 笔（USD / JPY）
```

不能把不同币种直接相加。

补充校验：

- `converted_amount` 和 `converted_currency` 必须成对出现；
- `exchange_rate_date` 依赖 `exchange_rate`；
- 换算允许合理舍入，不做强制完全相等。

### 6.7 退款

当前 `amount >= 0`，模型不支持退款。

本期建议明确不做退款。如果未来需要，新增：

```text
direction = charge | refund
```

统计时 refund 做减项。

**不要用负数金额隐晦表达退款。**

---

## 7. Hotel、Transport 与 Place 的边界

### 7.1 Hotel 暂不关联 Place

Hotel 已经保存：

- 地址；
- 经纬度；
- 地理编码结果；
- 地图点位。

如果现在增加 `Hotel.place_id`，会立刻引入双位置来源：

```text
Hotel.address / Hotel.lat / Hotel.lon
Place.city / Place.lat / Place.lon
```

因此本期建议：

- Hotel 地址和坐标明确为“预订快照”；
- 可以提供“从酒店保存为地点”，但不自动建立关联；
- 地图继续使用 Hotel 自己的坐标；
- 等确实有“酒店与活动共享同一个地点实体”的需求时，再评审 `Hotel.place_id`，并预先定义位置优先级。

### 7.2 Transport 不关联 Place

交通继续使用：

- IATA；
- 机场/车站文本；
- 现有机场/车站参考数据；
- `origin/destination` 自由文本或代码。

不建议把每次交通起降点规范化为 Place，否则 Place 会膨胀成全球地点库，并与现有参考数据重复。

Place 中的 `airport/train_station/...` 类型仅用于用户收藏。

---

## 8. Note、Attachment 与未来 Photo

### 8.1 Note

Note 继续作为自由文本内容：

- 可以关联 Trip；
- 不进入时间线；
- 在行程详情独立展示。

如果未来需要“记录级笔记”，复用 Attachment 的 `resource_type/resource_id` 模式，不要同时维护 `trip_id` 和另一套归属。

### 8.2 Attachment

保持现有实现：

- 二进制走 StorageProvider；
- 数据库只存元数据；
- `resource_type/resource_id` 作为多态归属；
- 不进入时间线。

### 8.3 Photo（未来）

Photo 建议作为 Attachment 的扩展，而不是另起一套记录体系：

- 关联 Trip / Activity / Place；
- 带 `captured_at`、经纬度等元数据；
- 不进入时间线。

本期不实现。

---

## 9. API、AI、MCP 兼容策略

### 9.1 旧 TripItem API

短期保留门面，避免前端和已有调用直接失效：

- `POST /trips/{id}/items` 收到 place 请求时，内部创建 `visit` Activity；
- 返回的 `item_type` 变为 `activity`；
- `DELETE /trips/{id}/items/{item_id}` 改为“清空源记录 trip_id”的语义；
- 不再支持通过 TripItem 直接修改源记录时间。

长期稳定后再删除旧 place 语义。

### 9.2 AI

- `add_place_to_trip` 改为创建 `visit` Activity；
- 创建前查询同行程、同地点活动；
- 不阻止合法的再次到访，但要避免重复提交同一事件；
- `create_place` 只创建地点库条目，不再提示“之后还要加入行程”；
- Expense 支持来源关联，并遵守“有来源时行程派生”的规则；
- 用户只是说“票价多少”时，不自动再建 Expense。

### 9.3 MCP

- Place 仍然是地点库记录，不再有独立行程成员概念；
- Activity 写入支持 `visit`；
- Expense 写入支持来源关联；
- 文档同步说明“实际花费只由 Expense 统计”。

### 9.4 规格同步

现有规格 `#15/#16` 的示例仍把 Place 直接列为 TripItem。实施前应更新规格或新增 ADR，明确：

- Trip 可以聚合并展示 Place/Expense/Note；
- 但 TripItem 只表示时间线事件；
- Place 通过 Activity 进入行程；
- Expense/Note 在行程详情独立分区展示。

否则后续开发很容易按旧规格把 place item 加回来。

---

## 10. 数据迁移

### 10.1 迁移原则

- 所有表结构变更通过 Alembic；
- 不使用本地常驻数据库做验证；测试使用 SQLite 内存库；
- 迁移保守处理历史数据，不猜用户意图；
- 地点本身和实际花费不删除。

当前 head：`0024_places_activities`。

### 10.2 Place trip item 迁移

对每条 `trip_items.item_type='place'`：

1. 查找同 `trip_id`、同 `place_id` 的 Activity；
2. **只有开始/结束时间完全一致的 Activity** 才视为重复项并合并；
3. 其他情况创建一条独立 `visit` Activity：
   - `name` 取 Place 名称；
   - `type='visit'`；
   - 保留 `trip_id`、`place_id`、`start_at/end_at`；
   - 保留原排序位置；
4. 删除原 place item；
5. 迁移后服务层不再允许产生 `item_type='place'`。

时间不同的历史数据一律保留，不做自动合并，避免误删真实到访。

### 10.3 Expense 迁移

- 新增 `source_type/source_id`，默认全部为空；
- 不按金额或描述自动关联历史记录；
- 由用户在 UI 中手工关联；
- 统计在关联前继续按现有口径工作。

### 10.4 删除 TripItem 时间列

在代码不再读写 `trip_items.start_at/end_at` 后，单独迁移删除：

```text
trip_items.start_at
trip_items.end_at
```

不要和 Place 数据迁移放在同一个 migration 里，降低回滚和排查难度。

---

## 11. 实施顺序

### 阶段 1：收读取口径，消除时间漂移

- TripItemRead 时间改由源实体计算；
- 排序改由源实体时间驱动；
- 禁止通过 TripItem 直接改时间；
- 增加 `ensure_timeline_items()`；
- 补时间一致性测试。

这一步风险低，先消除“两个时间可能不一致”。

### 阶段 2：Place → visit Activity

- Activity 增加 `visit` 类型；
- legacy place item 保守迁移；
- Place 加入行程改为创建 Activity；
- 活动卡片显示地点；
- 行程详情增加“未安排”分组；
- 更新 AI 和旧 API 门面；
- 补重复到访、迁移去重测试。

### 阶段 3：Expense 关联与统计

- Expense 增加 `source_type/source_id` 和索引；
- 有来源时派生并同步 `trip_id`；
- 来源删除后保留开销和行程快照；
- 记录详情增加“记一笔开销”；
- 行程详情增加花费汇总区；
- 统计按报告币种汇总，未换算单列；
- 更新 AI/MCP；
- 补多币种、来源删除、统计口径测试。

### 阶段 4：清理与增强

- 删除 `trip_items.start_at/end_at`；
- 删除旧 place item 代码和测试；
- 补 Place/Activity/Expense 导入；
- 再做地理编码、地图图层等增强；
- `Hotel.place_id` 留到确有需求时再评审。

---

## 12. 验收标准

完成后应满足：

- 时间线只出现 Transport / Hotel / Activity；
- 不再出现 `item_type='place'` 的 TripItem；
- 同一行程可以在不同时间多次到访同一 Place；
- 时间完全相同的 legacy place item + Activity 会合并，时间不同的不会误删；
- 活动卡片能显示并跳转关联地点；
- 修改 Activity 时间后，时间线立即变化，不需要同步另一份时间字段；
- 不能通过 TripItem API 把活动时间改成与 Activity 不一致；
- 记录上的 price 不进入总花费统计；
- 创建记录不会因为填了 price 就自动生成 Expense；
- 一条来源记录可以关联多笔 Expense；
- 来源记录换行程后，关联 Expense 的行程同步变化；
- 来源记录删除后，Expense 保留在原行程，但来源变空；
- 多币种开销不会被直接相加，未换算部分单独显示；
- 行程详情明确区分“时间线 / 花费 / 笔记附件”；
- AI 不再生成 place 类型的时间线条目；
- 导出再导入后，Place、Activity、Expense 的关联能恢复。

---

## 13. 明确不做的事

以下方案不建议采用：

1. **不把所有类型合并成一张通用 Record 大表**：会失去字段约束和业务语义。
2. **不对 `(trip_id, place_id)` 做唯一约束**：会阻止合法的重复到访。
3. **不让 Place 直接成为 TripItem**：会造成活动和地点重复。
4. **不让 Expense 和记录 price 各自独立统计**：会形成两个总花费。
5. **不自动把 price 转成 Expense**：票面价不等于实际支出。
6. **不按金额自动关联历史 Expense**：容易错误归因。
7. **不让 TripItem 保存权威时间**：会持续产生同步和漂移问题。
8. **不把 Expense/Note 塞进时间线**：行程详情应分区展示。
9. **不把交通起降点全部规范化为 Place**：会与现有参考数据和 IATA 体系重复。

---

## 14. 决策记录摘要

| 决策 | 结论 |
|---|---|
| Place 是否保留 | 保留，作为地点库与地理引用 |
| Place 是否进入时间线 | 否，通过 Activity 表达到访 |
| 同一地点能否多次到访 | 可以，按事件去重，不按地点去重 |
| TripItem 类型 | 仅 transport / hotel / activity |
| TripItem 是否保存时间 | 否，时间由源实体提供 |
| 记录 price 的角色 | 票面/预订参考价，不参与花费统计 |
| Expense 的角色 | 实际花费唯一来源 |
| Expense 来源关联 | 可选，多对一，不自动创建 |
| 有来源 Expense 的行程 | 从来源派生并同步 |
| 来源删除后的 Expense | 保留，清除来源，保留行程快照 |
| Hotel/Transport 与 Place | 暂不强制关联 |
| Note/Attachment | 不进入时间线 |
