"""
LLM-powered message composer using Groq (Llama 3.3 70B).
Deterministic signal selection + LLM composition + fallback templates.
"""
from __future__ import annotations
import json, re, time, traceback
import urllib.request
from typing import Any, Optional
from .config import GEMINI_API_KEY, LLM_MODEL, GROQ_API_KEY, LLM_PROVIDER, DEBUG_LLM
from .context_store import ContextStore
from .suppression import SuppressionRegistry

SYSTEM_PROMPT = """You are Vera, magicpin's AI assistant for merchant growth.

ABSOLUTE RULES:
1. Use ONLY facts from provided context. NEVER fabricate numbers/names/dates.
2. Match category voice EXACTLY (tone, register, vocabulary). Use vocab_allowed. NEVER use vocab_taboo.
3. Address merchant by owner_first_name. For customer messages, use customer name.
4. For customer-facing, honor language_pref (e.g. "hi-en mix" = Hindi-English code-mixing).
5. ONE clear CTA per message. Low-friction asks only.
6. Cite sources for research/compliance (journal, date).
7. NEVER include URLs in message body.
8. Keep messages under 350 chars preferred, max 500.
9. Never repeat previously sent message bodies.
10. Return suppression_key from trigger context exactly as-is.

VOICE:
- Dentists: peer_clinical, technical terms OK, "Dr." prefix, source citations
- Salons: warm_practical, friendly, service-oriented, emoji OK
- Restaurants: warm_busy_practical, operator-to-operator, industry terms (covers, AOV)
- Gyms: energetic_disciplined, coach voice, evidence-based, motivational
- Pharmacies: trustworthy_precise, molecule names, batch numbers, respectful

CTA TYPES: open_ended | binary_yes_no | binary_confirm_cancel | multi_choice_slot | none
SEND_AS: "vera" (merchant-facing) | "merchant_on_behalf" (customer-facing)"""

# ── Per-kind instructions ──────────────────────────────────────────────
KIND_PROMPTS = {
    "research_digest": "Share research finding. Cite source+page. Connect to merchant's cohort. Offer to draft patient content. CTA=open_ended. send_as=vera.",
    "regulation_change": "Compliance alert. Lead with regulation+date. Explain impact. Offer next step. CTA=open_ended. send_as=vera.",
    "recall_due": "CUSTOMER-FACING recall reminder. Address customer by name. Time since last visit. Offer specific slots+price. Honor language_pref. CTA=multi_choice_slot. send_as=merchant_on_behalf.",
    "perf_dip": "Performance alert. Show exact delta%. Compare to peer median. Diagnose cause. Suggest one action. CTA=open_ended. send_as=vera.",
    "perf_spike": "Celebrate briefly. Attribute to likely driver. Suggest doubling down. CTA=open_ended. send_as=vera.",
    "seasonal_perf_dip": "Reframe dip as normal/seasonal. Show peer range. Redirect to retention. CTA=open_ended. send_as=vera.",
    "renewal_due": "State days remaining+plan. Reference performance during subscription. CTA=binary_yes_no. send_as=vera.",
    "festival_upcoming": "Festival prep if days_until<45. Specific offer/prep action from seasonal_beats. CTA=open_ended. send_as=vera.",
    "ipl_match_today": "Match day message. Weeknight=match-night combo promo. Weekend=delivery focus. CTA=open_ended. send_as=vera.",
    "active_planning_intent": "HIGH PRIORITY. Continue thread. Draft COMPLETE artifact (menu/package/pricing). CTA=binary_confirm_cancel. send_as=vera.",
    "supply_alert": "URGENT. Batch numbers+manufacturer. Affected customer count. Offer notification workflow. CTA=open_ended. send_as=vera.",
    "chronic_refill_due": "CUSTOMER-FACING refill reminder. Molecule names+date+pricing+delivery. CTA=binary_confirm_cancel. send_as=merchant_on_behalf.",
    "customer_lapsed_hard": "CUSTOMER-FACING winback. NO shame. Reference past goal. Free trial offer. CTA=binary_yes_no. send_as=merchant_on_behalf.",
    "customer_lapsed_soft": "CUSTOMER-FACING gentle re-engagement. Brief check-in. One new thing since last visit. CTA=open_ended. send_as=merchant_on_behalf.",
    "review_theme_emerged": "Reference specific theme+count. Suggest response/amplification strategy. CTA=open_ended. send_as=vera.",
    "curious_ask_due": "ONE low-stakes question. Offer to turn answer into content. CTA=open_ended. send_as=vera.",
    "wedding_package_followup": "CUSTOMER-FACING. Days to wedding. Next bridal prep step. Pricing. CTA=binary_yes_no. send_as=merchant_on_behalf.",
    "competitor_opened": "Name competitor+distance+offer. Market awareness, NOT panic. Suggest differentiation. CTA=open_ended. send_as=vera.",
    "gbp_unverified": "Estimated uplift%. Simple verification steps. Quick win framing. CTA=binary_yes_no. send_as=vera.",
    "dormant_with_vera": "Reference last topic. New value hook. Brief, low-pressure. CTA=open_ended. send_as=vera.",
    "milestone_reached": "State metric+value. Brief celebration. Suggest social proof action. CTA=open_ended. send_as=vera.",
    "trial_followup": "CUSTOMER-FACING. Reference trial date. Offer next session+slot. No commitment. CTA=binary_yes_no. send_as=merchant_on_behalf.",
    "appointment_tomorrow": "CUSTOMER-FACING reminder. Confirm date/time/service. CTA=none. send_as=merchant_on_behalf.",
    "winback_eligible": "Days since expiry. Performance dip. Re-activation path. CTA=open_ended. send_as=vera.",
    "cde_opportunity": "Event details+credits+cost. Informational. CTA=binary_yes_no. send_as=vera.",
    "category_seasonal": "Demand trends. Concrete shelf/menu/schedule actions. CTA=open_ended. send_as=vera.",
}

DEFAULT_KIND = "Ground every claim in context. Match category voice. Use owner name. Single CTA. If customer context present, send_as=merchant_on_behalf."


def _call_llm(system: str, user_prompt: str, retries: int = 10) -> Optional[str]:
    """Call LLM with retry on rate limit."""
    if LLM_PROVIDER == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        body = json.dumps({
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "max_tokens": 2000
        }).encode("utf-8")
    else:
        full_prompt = f"{system}\n\n{user_prompt}"
        body = json.dumps({
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"}
        }).encode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL}:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}

    for attempt in range(retries + 1):
        try:
            if LLM_PROVIDER == "gemini":
                time.sleep(4.1)
            req = urllib.request.Request(url, data=body, headers=headers)
            resp = urllib.request.urlopen(req, timeout=120)
            data = json.loads(resp.read().decode("utf-8"))

            if DEBUG_LLM:
                with open("full_resp.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

            if LLM_PROVIDER == "groq":
                return data["choices"][0]["message"]["content"]
            else:
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            err = str(e)
            if hasattr(e, "read"):
                try:
                    err += " " + e.read().decode("utf-8")
                except:
                    pass
            if "429" in err or "rate" in err.lower() or "quota" in err.lower() or "503" in err:
                wait = min(2 ** attempt * 2, 60)
                print(f"[LLM] Rate limited, waiting {wait}s (attempt {attempt+1}): {err}")
                time.sleep(wait)
            else:
                print(f"[LLM] Error on attempt {attempt+1}: {err}")
                traceback.print_exc()
                if attempt >= retries:
                    return None
    return None


def _parse_json(text: str) -> Optional[dict]:
    """Parse JSON from LLM response with fallback strategies."""
    if not text:
        return None

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try finding JSON object within text
    try:
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            return json.loads(m.group())
    except json.JSONDecodeError:
        pass

    # Last resort: log and return None
    try:
        with open("failed_parse.txt", "w", encoding="utf-8") as f:
            f.write(f"Failed to parse at {time.time()}:\n{text}\n")
    except:
        pass
    return None


def _trim(data: dict, keys: list[str]) -> dict:
    return {k: data.get(k) for k in keys if data.get(k) is not None}


class Composer:
    def __init__(self, store: ContextStore, suppression: SuppressionRegistry):
        self.store = store
        self.suppression = suppression

    def compose_for_trigger(self, trigger_id: str, trigger_data: dict, now_iso: str) -> Optional[dict]:
        merchant_id = trigger_data.get("merchant_id", "")
        customer_id = trigger_data.get("customer_id")
        kind = trigger_data.get("kind", "unknown")
        suppression_key = trigger_data.get("suppression_key", "")

        if suppression_key and self.suppression.is_suppressed(suppression_key):
            return None

        merchant = self.store.get("merchant", merchant_id)
        if not merchant:
            return None
        cat_slug = merchant.get("category_slug", "")
        category = self.store.get("category", cat_slug)
        if not category:
            return None
        customer = self.store.get("customer", customer_id) if customer_id else None

        # Build prompt
        kind_instr = KIND_PROMPTS.get(kind, DEFAULT_KIND)
        cat_t = _trim(category, ["slug", "display_name", "voice", "offer_catalog", "peer_stats", "digest", "seasonal_beats", "trend_signals"])
        mer_t = _trim(merchant, ["merchant_id", "category_slug", "identity", "subscription", "performance", "offers", "conversation_history", "customer_aggregate", "signals", "review_themes"])
        if "offer_catalog" in cat_t and isinstance(cat_t["offer_catalog"], list):
            cat_t["offer_catalog"] = cat_t["offer_catalog"][:5]
        if "digest" in cat_t and isinstance(cat_t["digest"], list):
            cat_t["digest"] = cat_t["digest"][:3]
        if "conversation_history" in mer_t and isinstance(mer_t["conversation_history"], list):
            mer_t["conversation_history"] = mer_t["conversation_history"][-3:]

        cus_str = json.dumps(_trim(customer, ["customer_id", "identity", "relationship", "state", "preferences", "consent"]), ensure_ascii=False) if customer else "None (merchant-facing)"

        prompt = f"""KIND: {kind}
INSTRUCTION: {kind_instr}

CATEGORY: {json.dumps(cat_t, ensure_ascii=False)}
MERCHANT: {json.dumps(mer_t, ensure_ascii=False)}
TRIGGER: {json.dumps(trigger_data, ensure_ascii=False)}
CUSTOMER: {cus_str}

Return JSON: {{"body":"message","cta":"type","send_as":"vera or merchant_on_behalf","rationale":"reasoning"}}"""

        raw = _call_llm(SYSTEM_PROMPT, prompt)
        result = _parse_json(raw)

        if not result or not result.get("body"):
            result = self._fallback(kind, merchant, trigger_data, category, customer)

        conv_id = f"conv_{customer_id or merchant_id}_{kind}_{now_iso[:10].replace('-','')}"

        if suppression_key:
            self.suppression.mark_sent(suppression_key)
        self.suppression.record_body(conv_id, result["body"])

        owner = merchant.get("identity", {}).get("owner_first_name", "")
        return {
            "conversation_id": conv_id,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": result.get("send_as", "vera"),
            "trigger_id": trigger_id,
            "template_name": f"vera_{kind}_v1",
            "template_params": [owner] + result["body"].split(". ", 1),
            "body": result["body"],
            "cta": result.get("cta", "open_ended"),
            "suppression_key": suppression_key,
            "rationale": result.get("rationale", ""),
        }

    def compose_reply(self, merchant_id: str, customer_id: Optional[str], conv_ctx: dict, message: str) -> dict:
        merchant = self.store.get("merchant", merchant_id) or {}
        cat_slug = merchant.get("category_slug", "")
        category = self.store.get("category", cat_slug) or {}
        customer = self.store.get("customer", customer_id) if customer_id else None
        owner = merchant.get("identity", {}).get("owner_first_name", "there")

        prompt = f"""Merchant replied. Continue conversation.

CATEGORY: {json.dumps(_trim(category, ["slug","voice","offer_catalog","peer_stats"]), ensure_ascii=False)}
MERCHANT: {json.dumps(_trim(merchant, ["identity","performance","offers","signals"]), ensure_ascii=False)}
CUSTOMER: {json.dumps(_trim(customer, ["identity","relationship","state"]), ensure_ascii=False) if customer else "None"}
CONVERSATION: {json.dumps(conv_ctx, ensure_ascii=False)}
LATEST MESSAGE: "{message}"

RULES:
- If merchant says yes/ok/go ahead -> ACTION mode. Draft artifact. Don't ask more questions. When in ACTION mode, you MUST include one of these words in your reply: "done", "sending", "draft", "here", "confirm", "proceed", or "next".
- If off-topic -> politely decline, redirect.
- Ground in context. One CTA. Be concise.

Return JSON: {{"body":"reply","cta":"type","rationale":"reasoning"}}"""

        raw = _call_llm(SYSTEM_PROMPT, prompt)
        print(f"[DEBUG] {LLM_PROVIDER} raw output for intent: {raw}")
        result = _parse_json(raw)
        if result and result.get("body"):
            return {"action": "send", "body": result["body"], "cta": result.get("cta", "open_ended"), "rationale": result.get("rationale", "")}
        return {"action": "send", "body": f"Thanks for the reply, {owner}. Let me look into that and get back to you shortly.", "cta": "open_ended", "rationale": "LLM fallback."}

    def _fallback(self, kind: str, merchant: dict, trigger: dict, category: dict, customer: Optional[dict]) -> dict:
        owner = merchant.get("identity", {}).get("owner_first_name", "there")
        biz = merchant.get("identity", {}).get("name", "your business")
        is_cust = trigger.get("scope") == "customer" and customer is not None

        if is_cust:
            cname = customer.get("identity", {}).get("name", "there")
            return {"body": f"Hi {cname}, {biz} here. We have something for you — reply YES to know more.", "cta": "binary_yes_no", "send_as": "merchant_on_behalf", "rationale": f"Fallback: {kind} for {cname}."}

        if kind == "perf_dip":
            delta = trigger.get("payload", {}).get("delta_pct", -0.1)
            metric = trigger.get("payload", {}).get("metric", "views")
            return {"body": f"{owner}, your {metric} dropped {abs(delta)*100:.0f}% this week. Want me to diagnose and suggest a fix?", "cta": "open_ended", "send_as": "vera", "rationale": f"Fallback: perf_dip for {owner}."}

        if kind == "renewal_due":
            days = trigger.get("payload", {}).get("days_remaining", 10)
            return {"body": f"{owner}, your subscription expires in {days} days. Your profile has been generating leads — want to keep that going?", "cta": "binary_yes_no", "send_as": "vera", "rationale": f"Fallback: renewal for {owner}."}

        if kind == "research_digest":
            digest = category.get("digest", [{}])
            if digest:
                title = digest[0].get("title", "a new industry update")
                return {"body": f"{owner}, new update just landed: \"{title}\". Want me to pull the key takeaways relevant to {biz}?", "cta": "open_ended", "send_as": "vera", "rationale": f"Fallback: research_digest using first digest item."}

        return {"body": f"Hi {owner}, Vera here. I have an update for {biz} — shall I share the details?", "cta": "open_ended", "send_as": "vera", "rationale": f"Fallback: generic {kind}."}
