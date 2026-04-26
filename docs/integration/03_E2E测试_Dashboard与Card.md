# ATWA E2E 测试 — 03 Dashboard 与 Session Card

> 覆盖场景：Playwright 环境配置、Dashboard 基础功能、Session Card 交互
> 对应文件：`playwright.config.ts`、`test_dashboard.spec.ts`、`test_session_card.spec.ts`

---

## 4.1 Playwright 环境配置

**文件**：`tests/e2e/playwright.config.ts`

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:8743',
    headless: true,
    viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'python -m uvicorn server.main:app --port 8743',
    port: 8743,
    reuseExistingServer: false,
    timeout: 15000,
  },
});
```

---

## 4.2 Page Object Model

**文件**：`tests/e2e/pages/DashboardPage.ts`

所有 E2E 测试通过 `DashboardPage` 操作 UI，禁止在测试文件中直接使用裸 selector，方便后续统一维护。

```typescript
export class DashboardPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/');
    await this.page.waitForSelector('[data-testid="dashboard"]');
  }

  async getSessionCards() {
    return this.page.locator('[data-testid="session-card"]').all();
  }

  async getCardByPaneId(paneId: string) {
    return this.page.locator(`[data-testid="session-card"][data-pane-id="${paneId}"]`);
  }

  async clickFilter(filter: 'all' | 'attention' | 'running' | 'done' | 'dead') {
    await this.page.click(`[data-testid="filter-${filter}"]`);
  }

  async editDisplayName(paneId: string, newName: string) {
    const card = await this.getCardByPaneId(paneId);
    await card.locator('[data-testid="display-name"]').click();
    await card.locator('[data-testid="display-name-input"]').fill(newName);
    await card.locator('[data-testid="display-name-input"]').press('Enter');
  }

  async clickQuickReply(paneId: string, reply: 'yes' | 'no') {
    const card = await this.getCardByPaneId(paneId);
    await card.locator(`[data-testid="quick-reply-${reply}"]`).click();
  }

  async confirmSend() {
    await this.page.locator('[data-testid="send-confirm-btn"]').click();
  }
}
```

> **重要**：前端组件必须为所有可交互元素添加 `data-testid` 属性，这是 E2E 测试的唯一依赖，不得在重构时删除。

---

## 4.3 Dashboard 基础功能

**文件**：`tests/e2e/test_dashboard.spec.ts`

---

#### TC-E2E-DASH-001：Dashboard 正常加载

**目的**：验证 Dashboard 页面在 2 秒内完成加载并展示 session 列表。

**测试步骤**：
```typescript
test('Dashboard 正常加载', async ({ page }) => {
  const dashboard = new DashboardPage(page);
  await dashboard.goto();

  await expect(page.locator('[data-testid="dashboard-header"]')).toBeVisible();
  await expect(page.locator('[data-testid="session-list"]')).toBeVisible();
  await expect(page.locator('[data-testid="filter-bar"]')).toBeVisible();
});
```

**预期结果**：
- 页面在 2 秒内加载完成
- Header、session 列表、过滤栏均可见
- 无 console error（通过 `page.on('console', msg => ...)` 监听 error 级别）
- 无 network 请求返回 4xx/5xx

**失败排查**：
- 若页面空白：检查 `webServer` 是否启动成功，查看 Playwright 输出中的 server 启动日志
- 若 console error：检查前端是否有未处理的 Promise rejection，通常是 WebSocket 连接失败或 API 返回格式不符

---

#### TC-E2E-DASH-002：过滤器——仅显示需要处理的 session

**前置条件**：预置测试数据，包含：
- 2 个 `waiting_input` 状态的 pane
- 2 个 `active` 状态的 pane
- 1 个 `completed` 状态的 pane

**测试步骤**：
```typescript
test('过滤器：NEED ATTENTION', async ({ page }) => {
  const dashboard = new DashboardPage(page);
  await dashboard.goto();
  await dashboard.clickFilter('attention');

  const cards = await dashboard.getSessionCards();
  expect(cards.length).toBe(2);

  for (const card of cards) {
    await expect(card.locator('[data-testid="status-badge"]')).toHaveClass(/status-red/);
  }
});
```

**预期结果**：
- 只显示 2 张卡片
- 每张卡片状态标识为红色
- 过滤器按钮 `NEED ATTENTION` 处于选中状态（active 样式）

---

#### TC-E2E-DASH-003：过滤器切换不影响数据

**目的**：验证在不同过滤器之间切换后，切回 ALL 时所有 session 都恢复显示。

**测试步骤**：
```typescript
test('过滤器切换保留数据', async ({ page }) => {
  const dashboard = new DashboardPage(page);
  await dashboard.goto();

  const initialCount = (await dashboard.getSessionCards()).length;

  await dashboard.clickFilter('running');
  await dashboard.clickFilter('done');
  await dashboard.clickFilter('all');

  const finalCount = (await dashboard.getSessionCards()).length;
  expect(finalCount).toBe(initialCount);
});
```

**预期结果**：切回 ALL 后卡片数量与初始一致，无数据丢失。

---

#### TC-E2E-DASH-004：运行时信息展示

**目的**：验证每张卡片正确展示计时器、当前工具、token 用量。

**前置条件**：pane `%1` 处于 `tool_executing` 状态，当前工具为 `Write`，运行 3 分 20 秒，token 8000。

**测试步骤**：
```typescript
const card = await dashboard.getCardByPaneId('%1');

await expect(card.locator('[data-testid="elapsed-timer"]')).toContainText('3m');
await expect(card.locator('[data-testid="current-tool"]')).toContainText('Write');
await expect(card.locator('[data-testid="token-count"]')).toContainText('8k');
```

**预期结果**：
- 计时器显示 `3m 20s` 左右（允许 ±3 秒误差）
- 工具名显示 `Write`
- token 显示 `8k`

---

## 4.4 Session Card 交互

**文件**：`tests/e2e/test_session_card.spec.ts`

---

#### TC-E2E-CARD-001：waiting_input 时自动展开输入区

**目的**：验证 pane 进入 `waiting_input` 状态时，对应 card 自动展开输入区，无需用户手动点击。

**测试步骤**：
```typescript
test('waiting_input 自动展开输入区', async ({ page }) => {
  const dashboard = new DashboardPage(page);
  await dashboard.goto();

  // 触发状态变更（通过 API mock 或真实 daemon）
  await triggerWaitingInput(page, '%1');

  const card = await dashboard.getCardByPaneId('%1');

  // 输入区应自动可见，无需点击
  await expect(card.locator('[data-testid="input-area"]')).toBeVisible({ timeout: 2000 });
  await expect(card.locator('[data-testid="agent-prompt"]')).toBeVisible();
});
```

**预期结果**：
- 状态变更后 2 秒内输入区自动展开
- 显示 agent 的提示文本
- 快捷回复按钮可见

**失败排查**：
- 若输入区未自动展开：检查前端是否监听了 WebSocket 的 `session_update` 事件，并在 `status == "waiting_input"` 时触发展开逻辑
- 若 agent prompt 文本不显示：检查 `runtime_info.last_prompt` 字段是否由 daemon 正确填充

---

#### TC-E2E-CARD-002：展开/折叠第二层信息

**目的**：验证点击 Expand 按钮展开工具调用序列和错误摘要。

**测试步骤**：
```typescript
test('展开第二层信息', async ({ page }) => {
  const card = await dashboard.getCardByPaneId('%1');

  // 默认折叠
  await expect(card.locator('[data-testid="tool-history"]')).not.toBeVisible();

  // 点击展开
  await card.locator('[data-testid="expand-btn"]').click();
  await expect(card.locator('[data-testid="tool-history"]')).toBeVisible();

  // 再次点击折叠
  await card.locator('[data-testid="expand-btn"]').click();
  await expect(card.locator('[data-testid="tool-history"]')).not.toBeVisible();
});
```

**预期结果**：
- 默认折叠，点击后展开工具历史
- 再次点击收起，状态切换流畅

---

#### TC-E2E-CARD-003：status badge 颜色与状态对应

**目的**：验证所有关键状态的 badge 颜色正确渲染。

| 状态 | 预期颜色类 |
|------|-----------|
| `waiting_input` | `status-red` |
| `error_stopped` | `status-red` |
| `stuck` | `status-red` |
| `retry_loop` | `status-orange` |
| `slow_tool` | `status-orange` |
| `active` | `status-yellow` |
| `tool_executing` | `status-yellow` |
| `thinking` | `status-yellow` |
| `waiting_tool` | `status-blue` |
| `idle_running` | `status-blue` |
| `completed` | `status-green` |
| `terminated` | `status-green` |
| `crashed` | `status-black` |
| `killed` | `status-black` |

**测试步骤**：对每个状态预置对应数据，逐一验证 badge 的 CSS class。

**失败排查**：
- 若颜色类不匹配：检查前端的 `StatusBadge.tsx` 组件中的状态→颜色映射表是否覆盖所有状态
- 若 badge 不渲染：确认 `data-testid="status-badge"` 属性存在于组件根元素上
