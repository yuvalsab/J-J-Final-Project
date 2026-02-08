import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .fsm import AgentFSM
from .scoring import pick_two_distinct_errors
from .utils import ensure_sentence, normalize_error_id, safe_filename


class Runner:
    def __init__(self, repo, log, cfg, llm, selectors_module, export_dir: str):
        self.repo = repo
        self.log = log
        self.cfg = cfg
        self.llm = llm
        self.export_dir = export_dir
        self.selectors = selectors_module
        self.fsm = AgentFSM(repo=repo, llm=llm, log=log, cfg=cfg, selectors=selectors_module)

    def retrieve_case_context(self, lightning_name: str) -> Dict[str, Any]:
        self.log.log("info", "STEP", title="1) RETRIEVE FROM MONGO (RICH CONTEXT)")
        cols = self.repo.list_collections()
        self.log.log("info", "DB_COLLECTIONS", count=len(cols), collections=cols)

        ctx = self.repo.fetch_case_context(
            lightning_name,
            self.cfg.limit_errors,
            self.cfg.limit_events,
            self.cfg.limit_catheters,
        )
        self.log.log(
            "info",
            "FETCHED_CONTEXT",
            lightning_name=lightning_name,
            errors=len(ctx["errors"]),
            events=len(ctx["events"]),
            catheters=len(ctx["catheters"]),
            procedure=("YES" if ctx.get("procedure") else "NO"),
        )
        return ctx

    async def retrieve_case_context_async(self, lightning_name: str) -> Dict[str, Any]:
        return await asyncio.to_thread(self.retrieve_case_context, lightning_name)

    def act_and_log(self, lightning_name: str, decision: dict):
        self.log.log("info", "STEP", title="3) ACT (LOG ACTION + RESOLUTION TO MONGO)")

        now = datetime.utcnow()
        target_error_id = normalize_error_id(decision.get("target_error_id"))
        status = decision.get("status") if isinstance(decision.get("status"), str) else "SUCCESS"

        plan_src = decision.get("proposed_fix_plan")
        if not isinstance(plan_src, list) or not plan_src:
            plan_src = decision.get("suggested_next_queries")
        if not isinstance(plan_src, list):
            plan_src = []
        plan_src = [ensure_sentence(str(x), 140) for x in plan_src if str(x).strip()][:12]

        rc_src = decision.get("probable_root_causes")
        if not isinstance(rc_src, list):
            rc_src = []
        rc_src = [ensure_sentence(str(x), 140) for x in rc_src if str(x).strip()][:10]

        ev_src = decision.get("evidence")
        if not isinstance(ev_src, list):
            ev_src = []
        fixed_ev = []
        for x in ev_src:
            if isinstance(x, dict):
                eid = x.get("evidence_id")
                claim = x.get("claim")
                if isinstance(eid, str) and isinstance(claim, str) and eid.strip() and claim.strip():
                    fixed_ev.append({"evidence_id": eid.strip(), "claim": ensure_sentence(claim, 170)})

        action_doc = {
            "lightning_name": lightning_name,
            "timestamp": now,
            "type": "AI_ACTION",
            "status": status,
            "human_alert": bool(decision.get("human_alert", False)),
            "issue_id": decision.get("issue_id"),
            "issue_title": decision.get("issue_title"),
            "severity": decision.get("severity"),
            "target_error_id": target_error_id,
            "plan": [{"step": s, "status": "Open"} for s in plan_src],
            "evidence": fixed_ev,
            "root_causes": rc_src,
            "verification_rule": ensure_sentence(str(decision.get("verification_rule") or ""), 200),
            "missing_evidence": decision.get("missing_evidence"),
            "suggested_next_queries": decision.get("suggested_next_queries"),
            "verified_findings": decision.get("verified_findings"),
            "quality_meta": decision.get("quality_meta"),
            "suspect_catheters": decision.get("suspect_catheters"),
            "source": "llama3",
        }

        res_type = "AI_NEEDS_HUMAN_REVIEW" if status == "NEEDS_HUMAN_REVIEW" else "AI_RESOLVED"
        resolution_doc = {
            "lightning_name": lightning_name,
            "timestamp": now,
            "type": res_type,
            "target_error_id": target_error_id,
            "issue_id": decision.get("issue_id"),
            "issue_title": decision.get("issue_title"),
            "source": "agent",
        }

        self.repo.insert_action_and_resolution(lightning_name, action_doc, resolution_doc)
        self.log.log("info", "MONGO_INSERT", collection="AgentActions+AgentResolutions", status="ok")
        return action_doc, resolution_doc

    def verify(self, lightning_name: str, target_error_id: str):
        self.log.log("info", "STEP", title="4) VERIFY (MONGO)")
        hit = self.repo.verify_resolution(lightning_name, target_error_id)
        if hit:
            self.log.log("info", "VERIFIED", method="AgentResolutions")
            return {"verified": True, "method": "AgentResolutions", "resolution": hit}
        self.log.log("info", "NOT_VERIFIED", method="AgentResolutions")
        return {"verified": False, "method": "AgentResolutions"}

    def extract_procedure_id_for_export(self, ctx: Dict[str, Any], fallback: str) -> str:
        p = ctx.get("procedure") or {}
        pid = None
        if isinstance(p, dict):
            pid = p.get("procedure_id") or p.get("procedureId")
            extra = p.get("extra") if isinstance(p.get("extra"), dict) else {}
            pid = pid or extra.get("procedure_id") or extra.get("procedureId")
        pid = str(pid).strip() if pid is not None else ""
        return pid or fallback

    def export_results_json(self, procedure_id: str, results: Dict[str, Any]) -> str:
        pid = safe_filename(str(procedure_id))
        path = f"{self.export_dir.rstrip('/')}/{pid}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        self.log.log("info", "EXPORT_JSON", path=path)
        return path

    def _read_ui_template_html(self) -> str:
        base = self.export_dir.rstrip("/")

        env_path = (os.getenv("RCA_UI_TEMPLATE") or "").strip()
        candidates = []
        if env_path:
            candidates.append(env_path)

        candidates.append(os.path.join(base, "UI", "report_template.html"))
        candidates.append(os.path.join(base, "UI", "index.html"))
        candidates.append(os.path.join(base, "ui", "report_template.html"))
        candidates.append(os.path.join(base, "ui", "index.html"))

        for p in candidates:
            if p and os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return f.read()

        raise FileNotFoundError(
            "UI template not found. Expected one of: UI/report_template.html or UI/index.html "
            "or set RCA_UI_TEMPLATE env var."
        )

    def export_results_html(self, procedure_id: str, results: Dict[str, Any]) -> str:
        pid = safe_filename(str(procedure_id))
        path = f"{self.export_dir.rstrip('/')}/{pid}.html"

        html = self._read_ui_template_html()
        payload = json.dumps(results, ensure_ascii=False, default=str)

        if "{{REPORT_JSON}}" in html:
            html = html.replace("{{REPORT_JSON}}", payload)
        else:
            inject = f"<script>window.REPORT = {payload};</script>"
            if "</head>" in html:
                html = html.replace("</head>", f"{inject}\n</head>")
            else:
                html = inject + "\n" + html

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        self.log.log("info", "EXPORT_HTML", path=path)
        return path

    def run_two_cases(self, lightning_name: str, max_iters: Optional[int] = None):
        ctx = self.retrieve_case_context(lightning_name)
        errors = ctx["errors"]
        events = ctx["events"]

        e1, e2 = pick_two_distinct_errors(
            errors,
            self.cfg.weight_freq,
            self.cfg.weight_dur,
            self.cfg.weight_recency,
        )

        if not e1:
            self.log.log("info", "STEP", title="FINAL SUMMARY")
            final = {"error": "No errors found", "lightning_name": lightning_name}
            self.log.log("warning", "NO_ERRORS", lightning_name=lightning_name)
            pid = self.extract_procedure_id_for_export(ctx, lightning_name)
            self.export_results_json(pid, final)
            try:
                self.export_results_html(pid, final)
            except Exception as e:
                self.log.log("warning", "EXPORT_HTML_FAILED", error=str(e))
            return final

        self.log.log("info", "STEP", title="CASE 1")
        id1 = normalize_error_id(e1.get("error_id"))
        base1 = self.selectors.select_top_events_for_error(events, id1, limit=self.cfg.related_events_limit)
        d1 = self.fsm.run_sync(lightning_name, ctx, e1, base1, max_iters=max_iters)
        em1 = getattr(self.fsm, "last_evidence_map", None) or d1.get("evidence_map") or []
        a1, r1 = self.act_and_log(lightning_name, d1)
        v1 = self.verify(lightning_name, d1.get("target_error_id"))

        self.log.log("info", "STEP", title="CASE 2")
        if not e2:
            d2 = {
                "issue_id": f"{lightning_name}-NO-SECOND-ERROR",
                "issue_title": "No second distinct error",
                "severity": 3,
                "target_error_id": None,
                "status": "NEEDS_HUMAN_REVIEW",
                "human_alert": True,
                "probable_root_causes": [],
                "proposed_fix_plan": [ensure_sentence("Expand the retrieval window or adjust error selection to pick another distinct error_id.", 160)],
                "verification_rule": ensure_sentence("NEEDS_HUMAN_REVIEW: only one distinct error was found in the case data.", 180),
                "suggested_next_queries": [],
                "missing_evidence": [ensure_sentence("A second distinct error_id was not available for analysis.", 160)],
                "verified_findings": [],
                "suspect_catheters": [],
            }
            em2 = []
            a2, r2 = self.act_and_log(lightning_name, d2)
            v2 = {"verified": False, "reason": "no_second_error"}
            base2 = []
        else:
            id2 = normalize_error_id(e2.get("error_id"))
            base2 = self.selectors.select_top_events_for_error(events, id2, limit=self.cfg.related_events_limit)
            d2 = self.fsm.run_sync(lightning_name, ctx, e2, base2, max_iters=max_iters)
            em2 = getattr(self.fsm, "last_evidence_map", None) or d2.get("evidence_map") or []
            a2, r2 = self.act_and_log(lightning_name, d2)
            v2 = self.verify(lightning_name, d2.get("target_error_id"))

        self.log.log("info", "STEP", title="FINAL SUMMARY")

        evidence_map_by_case = {
            "case1": em1,
            "case2": em2,
        }

        final = {
            "lightning_name": lightning_name,
            "procedure_id": self.extract_procedure_id_for_export(ctx, lightning_name),
            "run_timestamp_utc": datetime.utcnow().isoformat(),
            "config": {
                "weight_freq": self.cfg.weight_freq,
                "weight_dur": self.cfg.weight_dur,
                "weight_recency": self.cfg.weight_recency,
                "evidence_item_max_tokens": self.cfg.evidence_item_max_tokens,
                "max_iters": self.cfg.max_iters,
            },
            "evidence_map": evidence_map_by_case.get("case1", []),
            "evidence_map_by_case": evidence_map_by_case,
            "case1": {
                "decision": d1,
                "verify": v1,
                "action_doc": a1,
                "resolution_doc": r1,
                "related_events": base1,
                "evidence_map": em1,
            },
            "case2": {
                "decision": d2,
                "verify": v2,
                "action_doc": a2,
                "resolution_doc": r2,
                "related_events": base2,
                "evidence_map": em2,
            },
        }

        self.export_results_json(final["procedure_id"], final)
        try:
            self.export_results_html(final["procedure_id"], final)
        except Exception as e:
            self.log.log("warning", "EXPORT_HTML_FAILED", error=str(e))

        return final

    async def run_two_cases_async(self, lightning_name: str, max_iters: Optional[int] = None):
        return await asyncio.to_thread(self.run_two_cases, lightning_name, max_iters)

    async def run_many_lightning_names_async(self, lightning_names: List[str], max_iters: Optional[int] = None):
        sem = asyncio.Semaphore(self.cfg.parallelism)

        async def one(name: str):
            async with sem:
                try:
                    return await self.run_two_cases_async(name, max_iters=max_iters)
                except Exception as e:
                    self.log.log("error", "RUN_FAILED", lightning_name=name, error=str(e))
                    return {"lightning_name": name, "error": str(e)}

        tasks = [asyncio.create_task(one(n)) for n in lightning_names]
        return await asyncio.gather(*tasks)
