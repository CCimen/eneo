from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from intric.files.file_models import FilePublic
from intric.jobs.job_models import JobInDb
from intric.users.user import UserSparse


@dataclass
class AppRun:
    created_at: datetime | None
    updated_at: datetime | None
    id: UUID | None
    job_id: UUID | None
    app_id: UUID
    user_id: UUID
    tenant_id: UUID
    input_files: list[FilePublic]
    input_text: str | None
    output: str | None
    user: UserSparse | None
    num_tokens_input: int | None
    num_tokens_output: int | None
    job: JobInDb | None
    completion_model_id: UUID
    output_type: str = "text"
    output_image_id: UUID | None = None
    output_image: FilePublic | None = None

    def update(
        self,
        *,
        job_id: UUID | None = None,
        output: str | None = None,
        output_type: str | None = None,
        output_image_id: UUID | None = None,
        num_tokens_input: int | None = None,
        num_tokens_output: int | None = None
    ):
        if job_id is not None:
            self.job_id = job_id

        if output is not None:
            self.output = output

        if output_type is not None:
            self.output_type = output_type

        if output_image_id is not None:
            self.output_image_id = output_image_id

        if num_tokens_input is not None:
            self.num_tokens_input = num_tokens_input

        if num_tokens_output is not None:
            self.num_tokens_output = num_tokens_output
