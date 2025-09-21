from intric.jobs.task_models import Transcription, UploadInfoBlob  # , DeepResearchPlanTask, DeepResearchExecuteTask
from intric.main.container.container import Container
from intric.websites.crawl_dependencies.crawl_models import CrawlTask
from intric.worker.crawl_tasks import crawl_task, queue_website_crawls
from intric.worker.upload_tasks import transcription_task, upload_info_blob_task
# from intric.worker.deep_research_worker import generate_research_plan, execute_research
from intric.worker.worker import Worker

worker = Worker()


@worker.function()
async def upload_info_blob(job_id: str, params: UploadInfoBlob, container: Container):
    return await upload_info_blob_task(job_id=job_id, params=params, container=container)


@worker.function()
async def transcription(job_id: str, params: Transcription, container: Container):
    return await transcription_task(job_id=job_id, params=params, container=container)


@worker.function()
async def crawl(job_id: str, params: CrawlTask, container: Container):
    return await crawl_task(job_id=job_id, params=params, container=container)


@worker.cron_job(weekday="fri", hour=23, minute=0)
async def crawl_all_websites(container: Container):
    return await queue_website_crawls(container=container)


# TODO: Enable once deep research worker imports are fixed
# @worker.function()
# async def generate_research_plan_task(job_id: str, params: DeepResearchPlanTask, container: Container):
#     """Generate research plan for a session."""
#     return await generate_research_plan(params.session_id)


# @worker.function()
# async def execute_research_task(job_id: str, params: DeepResearchExecuteTask, container: Container):
#     """Execute research for an approved session."""
#     return await execute_research(params.session_id)
