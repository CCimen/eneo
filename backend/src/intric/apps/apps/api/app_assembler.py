from typing import TYPE_CHECKING

from intric.ai_models.completion_models.completion_model import (
    ModelKwargs,
)
from intric.apps.apps.api.app_models import (
    AppPublic,
    InputField,
    InputFieldPublic,
    InputFieldType,
)
from intric.apps.apps.app import App
from intric.completion_models.presentation import CompletionModelAssembler
from intric.files.audio import AudioMimeTypes
from intric.files.file_models import (
    AcceptedFileType,
    FilePublic,
    FileRestrictions,
    Limit,
)
from intric.files.image import ImageMimeTypes
from intric.files.text import TextMimeTypes
from intric.prompts.api.prompt_assembler import PromptAssembler
from intric.transcription_models.presentation import TranscriptionModelPublic

if TYPE_CHECKING:
    from intric.main.models import ResourcePermission


class AppAssembler:
    def __init__(
        self,
        prompt_assembler: PromptAssembler,
    ):
        self.prompt_assembler = prompt_assembler

    def _get_accepted_file_types(self, input_type: InputFieldType):
        match input_type:
            case InputFieldType.TEXT_FIELD:
                return []
            case InputFieldType.TEXT_UPLOAD:
                return [
                    AcceptedFileType(mimetype=mimetype, size_limit=26214400)
                    for mimetype in TextMimeTypes.values()
                ]
            case InputFieldType.AUDIO_UPLOAD:
                return [
                    AcceptedFileType(mimetype=mimetype, size_limit=209715200)
                    for mimetype in AudioMimeTypes.values()
                ]
            case InputFieldType.AUDIO_RECORDER:
                return [
                    AcceptedFileType(mimetype=mimetype, size_limit=209715200)
                    for mimetype in AudioMimeTypes.values()
                ]
            case InputFieldType.IMAGE_UPLOAD:
                return [
                    AcceptedFileType(mimetype=mimetype, size_limit=20971520)
                    for mimetype in ImageMimeTypes.values()
                ]

    def _get_limit(self, input_type: InputFieldType):
        match input_type:
            case InputFieldType.TEXT_FIELD:
                return Limit(max_files=0, max_size=0)
            case InputFieldType.TEXT_UPLOAD:
                return Limit(
                    max_files=3,
                    max_size=104857600,
                )
            case InputFieldType.AUDIO_UPLOAD:
                return Limit(max_files=1, max_size=209715200)
            case InputFieldType.AUDIO_RECORDER:
                return Limit(max_files=1, max_size=209715200)
            case InputFieldType.IMAGE_UPLOAD:
                return Limit(max_files=2, max_size=41943040)

    def _get_input_fields(self, input_fields: list[InputField]):
        def _get_input_field(input_field: InputField):
            accepted_file_types = self._get_accepted_file_types(input_type=input_field.type)
            limit = self._get_limit(input_type=input_field.type)

            return InputFieldPublic(
                **input_field.model_dump(),
                accepted_file_types=accepted_file_types,
                limit=limit,
            )

        return [_get_input_field(input_field) for input_field in input_fields]

    def from_app_to_model(self, app: App, permissions: list["ResourcePermission"] = None):
        permissions = permissions or []

        input_fields = self._get_input_fields(app.input_fields)
        attachments = [FilePublic(**attachment.model_dump()) for attachment in app.attachments]
        prompt = (
            self.prompt_assembler.from_prompt_to_model(app.prompt)
            if app.prompt is not None
            else None
        )
        completion_model = CompletionModelAssembler.from_completion_model_to_sparse(
            completion_model=app.completion_model
        )
        model_kwargs = (
            app.completion_model_kwargs
            if app.completion_model_kwargs is not None
            else ModelKwargs()
        )
        allowed_attachments = FileRestrictions(
            accepted_file_types=[
                AcceptedFileType(mimetype=mimetype, size_limit=26214400)
                for mimetype in TextMimeTypes.values()
            ],
            limit=Limit(max_files=3, max_size=26214400),
        )

        transcription_model = TranscriptionModelPublic.from_domain(app.transcription_model)

        # Handle image generation model
        from intric.image_generation_models.presentation.image_generation_model_sparse import ImageGenerationModelSparse
        image_generation_model = None
        if app.image_generation_model is not None:
            # Convert domain model to sparse model
            # Handle enums and convert them to strings
            image_generation_model = ImageGenerationModelSparse(
                id=app.image_generation_model.id,
                created_at=app.image_generation_model.created_at,
                updated_at=app.image_generation_model.updated_at,
                name=app.image_generation_model.name,
                nickname=app.image_generation_model.nickname,
                family=str(app.image_generation_model.family.value) if hasattr(app.image_generation_model.family, 'value') else str(app.image_generation_model.family),
                org=str(app.image_generation_model.org.value) if app.image_generation_model.org and hasattr(app.image_generation_model.org, 'value') else str(app.image_generation_model.org) if app.image_generation_model.org else None,
                is_deprecated=app.image_generation_model.is_deprecated,
                stability=str(app.image_generation_model.stability.value) if hasattr(app.image_generation_model.stability, 'value') else str(app.image_generation_model.stability),
                hosting=str(app.image_generation_model.hosting.value) if hasattr(app.image_generation_model.hosting, 'value') else str(app.image_generation_model.hosting),
                description=app.image_generation_model.description,
                open_source=app.image_generation_model.open_source,
                litellm_model_name=app.image_generation_model.litellm_model_name,
            )

        return AppPublic(
            created_at=app.created_at,
            updated_at=app.updated_at,
            id=app.id,
            name=app.name,
            description=app.description,
            input_fields=input_fields,
            attachments=attachments,
            prompt=prompt,
            completion_model=completion_model,
            completion_model_kwargs=model_kwargs,
            allowed_attachments=allowed_attachments,
            published=app.published,
            permissions=permissions,
            transcription_model=transcription_model,
            data_retention_days=app.data_retention_days,
            output_type=app.output_type,
            image_generation_model=image_generation_model,
        )
