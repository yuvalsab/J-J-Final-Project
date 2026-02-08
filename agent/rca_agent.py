import os
from typing import Optional

from rca.config import load_config, config_from_dict
from rca.llm_gateway import LlmGateway
from rca.logger import JsonLogger
from rca.mongo_repo import MongoRepo
from rca import selectors
from rca.runner import Runner

# RCA Agent that ties together configuration, logging, MongoDB access,
# LLM gateway, and the runner to perform root cause analysis on cases.
class RcaAgent:
    def __init__(
        self,
        mongo_uri: str,
        db_name: str,
        export_dir: str = ".",
        config_path: Optional[str] = None,
        logger: Optional[JsonLogger] = None,
    ):
        self.log = logger or JsonLogger(level=os.getenv("RCA_LOG_LEVEL", "INFO"))

        raw = load_config(config_path)
        cfg = config_from_dict(raw)

        self.repo = MongoRepo(mongo_uri=mongo_uri, db_name=db_name)
        self.llm = LlmGateway(
            model=cfg.llm_model,
            temperature=cfg.llm_temperature,
            timeout_s=cfg.llm_timeout_s,
            retries=cfg.llm_retries,
        )

        self.runner = Runner(
            repo=self.repo,
            log=self.log,
            cfg=cfg,
            llm=self.llm,
            selectors_module=selectors,
            export_dir=export_dir,
        )
        self.cfg = cfg

    def run_two_cases(self, lightning_name: str, max_iters: Optional[int] = None):
        return self.runner.run_two_cases(lightning_name, max_iters=max_iters)

    async def run_two_cases_async(self, lightning_name: str, max_iters: Optional[int] = None):
        return await self.runner.run_two_cases_async(lightning_name, max_iters=max_iters)

    async def run_many_lightning_names_async(self, lightning_names, max_iters: Optional[int] = None):
        return await self.runner.run_many_lightning_names_async(lightning_names, max_iters=max_iters)
