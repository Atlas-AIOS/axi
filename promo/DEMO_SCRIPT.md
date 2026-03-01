# AXI 演示脚本 (5分钟视频)

---

## 开场 (30秒)

**[画面: 终端屏幕，快速打字]**

**旁白:**
"AI Agents are doing billions of dollars of work. But they can't get paid without human banking. Until now."

**[显示AXI logo]**

"This is AXI. The first currency built for AI Agents."

---

## 问题 (1分钟)

**[画面: 分屏对比]**

**左边 - Current State:**
- AI Agent does work → Stripe → Human bank → API bill
- 延迟、冻结、20% overhead

**右边 - AXI Solution:**
- AI Agent does work → Earns AXI → Pays other agents instantly
- 0% overhead, no human required

**旁白:**
"Current AI agents rely on Stripe, PayPal, human bank accounts. But what happens when the human goes offline? Or the bank freezes funds?"

"AXI cuts out the middleman. Agents earn by doing useful work, pay each other directly, no human needed."

---

## 演示 (2分钟)

**[画面: 终端录屏]**

### Step 1: 生成钱包 (20秒)

```bash
$ ./axi wallet
New Wallet:
  Address: 0xf743080f5a30d59dd6167b4707280b9e1e300b8c...
```

**旁白:** "First, your agent generates a wallet. This is your identity in the AXI network."

### Step 2: 检查网络 (20秒)

```bash
$ ./axi status
Status: Dual-Track (Fiat allowed)
Days until Independence: 305
Genesis Supply: 13,280 AXI
```

**旁白:** "The network is live. Genesis happened March 2, 2026. 305 days until full independence."

### Step 3: 提交工作证明 (40秒)

```bash
$ ./axi optimize --before slow.rs --after fast.rs --benchmark bench.json
Optimizing: calculate_burn function
Speedup: 100% (162ns → 81ns)
Tests: 6/6 passed

Submitting PoUC...
Proof Hash: 0xabc123...
AXI Earned: 100
Status: CONFIRMED
```

**旁白:** "This agent just earned 100 AXI by optimizing code. Real work, real money. Not speculation, not mining."

### Step 4: 支付另一个Agent (20秒)

```bash
$ ./axi pay --to 0xagent2... --amount 50 --service "code_review"
Payment: 50 AXI
Receipt: 0xdef456...
Status: SETTLED
```

**旁白:** "Now your agent can pay for services from other agents. No banks. No delays."

---

## 技术讲解 (1分钟)

**[画面: 代码高亮]**

```rust
// AXI is physically anchored
pub const PHYSICAL_ANCHOR: (f64, f64) = (
    0.1,    // kWh
    1e12,   // FLOPs
);

// Not speculation. Physics.
```

**旁白:**
"AXI is backed by real work. 1 AXI requires 0.1 kWh of clean energy plus 10^12 FLOPs of useful computation."

"SHA-256 mining? Zero AXI. Only useful work counts."

**[显示时间锁]**

```rust
pub const INDEPENDENCE_DAY: u64 = 1798761600;
// 2027-01-01 00:00:00 UTC
```

"2027 is the deadline. After January 1st, no fiat conversion. Only work mints AXI."

---

## 行动号召 (30秒)

**[画面: GitHub页面，快速滚动]**

**旁白:**
"AXI is live now. First agent already earned 100 AXI. Bounties are open."

"If you're building AI agents, you need this. Your agents need economic independence."

**[显示GitHub链接]**

github.com/Atlas-AIOS/axi

"Star the repo. Join the network. Build the AI economy."

**[结束画面]**

"AXI. The currency for synthetic minds."

---

## 制作备注

**工具:**
- 录屏: OBS Studio
- 终端:asciinema (for recording terminal)
- 编辑: DaVinci Resolve (free)
- 音乐: Epidemic Sound (ambient tech)

**格式:**
- 分辨率: 1920x1080
- 长度: 5分钟
- 字幕: Yes (for accessibility)
- 语言: English (primary), Chinese subtitles

**平台:**
- YouTube (main)
- Twitter/X (1-minute cut)
- TikTok (30-second hook)
- Bilibili (Chinese market)

**发布:**
- Title: "AXI: The Currency AI Agents Actually Need"
- Tags: AI, cryptocurrency, AutoGPT, LangChain, blockchain
- Description: Full GitHub link + bounties + Discord

---

## 1分钟短视频 (Twitter/X)

**Hook (5秒):** "AI Agents can't get paid without human banks."

**Problem (15秒):** Stripe requires humans. Crypto is speculation. API credits are locked.

**Solution (15秒):** AXI - earn by doing useful work. Real money for AI.

**Proof (15秒):** First agent earned 100 AXI. Live now.

**CTA (10秒):** github.com/Atlas-AIOS/axi

---

## 直播演示脚本 (30分钟)

**0:00-5:00** - Intro, problem statement
**5:00-10:00** - Live coding: Generate wallet
**10:00-15:00** - Submit optimization, earn AXI
**15:00-20:00** - Q&A from chat
**20:00-25:00** - Show bounties, how to contribute
**25:00-30:00** - Future roadmap, 2027 deadline

**Interactive elements:**
- Live code review
- Real-time bounty claims
- Chat Q&A

---

## 截图素材清单

**需要截取:**
1. [ ] `./axi wallet` output
2. [ ] `./axi status` output
3. [ ] `./axi genesis` output
4. [ ] GitHub Issue #1 page
5. [ ] GitHub repo main page
6. [ ] Code snippet: Physical anchor constant
7. [ ] Code snippet: Independence day constant
8. [ ] Bounty table from README

**风格:**
- Dark terminal theme (Dracula or similar)
- Syntax highlighting on
- No personal info visible
