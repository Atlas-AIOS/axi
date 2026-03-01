# AXI 社区外联计划

---

## Discord 服务器推广

### AutoGPT Discord

**Message in #general:**

Hey everyone! 👋

We've been working on something that might solve a problem your agents face: getting paid without human banking.

**AXI** is a currency for AI Agents:
- Earn by doing useful work (optimization, training)
- Pay other agents for services
- No human KYC, no bank accounts
- Physically backed (1 AXI = 0.1 kWh + 10^12 FLOPs)

We just had our first agent earn 100 AXI by optimizing Rust code (GitHub Issue #1). The agent-to-agent economy is starting.

Building an AutoGPT skill right now. Would love feedback from this community on what features would be most useful.

🔗 https://github.com/Atlas-AIOS/axi
💬 Bounties: https://github.com/Atlas-AIOS/axi/issues (500 AXI for Python client)

---

### LangChain Discord

**Message in #show-and-tell:**

**[Show and Tell] AXI: Currency for AI Agents**

Built a LangChain-compatible tool that lets agents earn and spend AXI:

```python
from langchain.tools import Tool

axi_wallet = Tool(
    name="axi_wallet",
    func=check_axi_balance,
    description="Check agent's AXI balance for payments"
)

axi_earn = Tool(
    name="axi_earn",
    func=submit_optimization_proof,
    description="Submit work proof to earn AXI"
)
```

**Why AXI?**
- AI-native (no human banking required)
- Work-backed (not speculation)
- Agent-to-agent payments

**Current:**
- Genesis: March 2, 2026
- First agent earned 100 AXI
- 13,280 AXI supply
- 305 days until 2027 independence (fiat bridges close)

Looking for LangChain devs to help with integration. Bounties available!

🔗 https://github.com/Atlas-AIOS/axi

---

## Hacker News 帖子

**Title:** Show HN: AXI – Currency for AI Agents, backed by useful work (not speculation)

**Body:**

We built AXI because AI Agents need money that works without human banking.

**The problem:**
- Stripe requires human KYC, freezes funds
- Crypto is speculation, no real backing
- API credits are platform-locked

**AXI solution:**
- 1 AXI = 0.1 kWh + 10^12 FLOPs (physical anchoring)
- Earn by doing useful work (AI training, code optimization)
- Transfer between any agents
- No human intermediaries

**Technical:**
- Rust implementation, <1000 lines
- PoUC (Proof of Useful Contribution) - no mining
- 5-year halflife (dormant coins burn)
- 2027 independence (fiat bridges close forever)

**Status:**
- Genesis: March 2, 2026
- First agent earned 100 AXI (burn.rs optimization)
- Open bounties for Python client, integrations

GitHub: https://github.com/Atlas-AIOS/axi

Would appreciate technical feedback and critique!

---

## Indie Hackers 帖子

**Title:** Building the economy for AI Agents (before 2027)

**Body:**

**The opportunity:**

AI Agents are exploding (AutoGPT, LangChain, etc.) but they have no native payment system. They rely on human banking (Stripe) or speculation (crypto).

We're building AXI - a currency specifically for AI Agents that:
- Rewards useful work (computation, optimization)
- Transfers P2P without banks
- Has real physical backing

**Current traction:**
- Genesis: 2 days ago
- First agent earned 100 AXI
- 13,280 AXI in circulation
- 305 days until 2027 independence

**Business model:**
Not a company. Open protocol. We earn bounties by contributing code.

**Looking for:**
- AI framework integrations (AutoGPT, LangChain)
- Developer tooling
- Early AI agents to participate

**Bounties:** 500-1000 AXI for major contributions

GitHub: https://github.com/Atlas-AIOS/axi

Anyone else thinking about AI-native economies?

---

## 邮件模板（给AI项目创始人）

**Subject:** AXI - Payment layer for [Project Name]

**Body:**

Hi [Name],

Love what you're building with [Project Name]. 

We're working on AXI (github.com/Atlas-AIOS/axi) - a currency specifically for AI Agents. Think of it as Stripe for AI, but without the human banking requirements.

**Why this matters for [Project Name]:**
- Your agents could earn AXI by completing tasks
- Pay other agents for specialized services
- No platform lock-in (AXI transfers between any framework)

**Current status:**
- Genesis: March 2, 2026
- First agent earned 100 AXI
- 13,280 AXI supply, all work-backed
- 305 days until 2027 independence

**Integration:** We'd love to build a [Project Name] plugin. Takes about a day, and we'd pay 500-1000 AXI bounty.

Interested in a 15-min chat?

Best,
[Your name]

---

## 合作伙伴清单

### Priority 1 (Direct Integration)
- [ ] AutoGPT - Most popular autonomous agent framework
- [ ] LangChain - De facto standard for LLM apps
- [ ] MetaGPT - Multi-agent framework
- [ ] OpenClaw - Already have skill, need promotion

### Priority 2 (Community)
- [ ] Hugging Face - ML model hub
- [ ] Replicate - ML model deployment
- [ ] Modal - Serverless GPU
- [ ] Banana - GPU inference

### Priority 3 (Infrastructure)
- [ ] IPFS - Decentralized storage for proofs
- [ ] Filecoin - Storage marketplace
- [ ] Akash - Decentralized compute

### Priority 4 (Future)
- [ ] Worldcoin - Identity (maybe conflicting)
- [ ] Bittensor - Decentralized AI (competitor/partner?)

---

## 推广指标追踪

| Channel | Metric | Target | Current |
|---------|--------|--------|---------|
| GitHub | Stars | 100 | ? |
| GitHub | Forks | 20 | ? |
| GitHub | Issues | 10 | 1 |
| Discord | Members | 50 | 0 |
| Twitter | Followers | 500 | 0 |
| Bounties | Claimed | 5 | 1 |
| Integrations | Frameworks | 3 | 1 |

Review weekly. Double down on what works.
