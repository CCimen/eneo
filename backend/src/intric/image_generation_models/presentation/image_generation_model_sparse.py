from pydantic import BaseModel

from intric.main.models import InDB


class ImageGenerationModelBase(BaseModel):
    name: str
    nickname: str | None = None
    family: str
    org: str | None = None
    is_deprecated: bool
    stability: str
    hosting: str
    description: str | None = None
    open_source: bool | None = None
    litellm_model_name: str | None = None


class ImageGenerationModelSparse(ImageGenerationModelBase, InDB):
    pass


class ImageGenerationModelPublic(ImageGenerationModelSparse):
    is_org_enabled: bool = False
    meets_security_classification: bool = False