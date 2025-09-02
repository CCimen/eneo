from typing import TYPE_CHECKING, Optional

from intric.ai_models.model_enums import (
    ModelFamily,
    ModelHostingLocation,
    ModelOrg,
    ModelStability,
)
from intric.base.base_entity import Entity
from intric.modules.module import Modules

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from intric.security_classifications.domain.entities.security_classification import (
        SecurityClassification,
    )
    from intric.users.user import UserInDB


class AIModel(Entity):
    def __init__(
        self,
        *,
        user: "UserInDB",
        nickname: Optional[str],
        name: str,
        family: ModelFamily,
        hosting: ModelHostingLocation,
        org: Optional[ModelOrg],
        stability: ModelStability,
        open_source: bool,
        description: Optional[str],
        hf_link: Optional[str],
        is_deprecated: bool,
        is_org_enabled: bool,
        id: Optional["UUID"] = None,
        created_at: Optional["datetime"] = None,
        updated_at: Optional["datetime"] = None,
        security_classification: Optional["SecurityClassification"] = None,
        default_enabled: bool = True,
        has_tenant_settings: bool = True,
    ):
        super().__init__(id, created_at, updated_at)
        self.user = user
        self.nickname = nickname
        self.name = name
        self.family = ModelFamily(family)
        self.hosting = ModelHostingLocation(hosting)
        self.org = ModelOrg(org) if org else None
        self.stability = ModelStability(stability)
        self.open_source = open_source
        self.description = description
        self.hf_link = hf_link
        self.is_deprecated = is_deprecated
        self.is_org_enabled = is_org_enabled
        self.security_classification = security_classification
        self.default_enabled = default_enabled
        self.has_tenant_settings = has_tenant_settings

    @property
    def is_locked(self):
        from intric.main.logging import get_logger
        logger = get_logger(__name__)
        
        if self.hosting == ModelHostingLocation.EU:
            if Modules.EU_HOSTING not in self.user.modules:
                logger.debug(f"Model {self.name} locked: EU hosting required but user doesn't have EU_HOSTING module")
                return True

        if self.hosting == ModelHostingLocation.SWE:
            if Modules.SWE_HOSTING not in self.user.modules:
                logger.debug(f"Model {self.name} locked: SWE hosting required but user doesn't have SWE_HOSTING module")
                logger.debug(f"Required module: {Modules.SWE_HOSTING}, User modules: {[str(m) for m in self.user.modules]}")
                return True

        logger.debug(f"Model {self.name} unlocked: hosting={self.hosting}")
        return False

    @property
    def can_access(self):
        from intric.main.logging import get_logger
        logger = get_logger(__name__)
        
        # Fallback logic for model access:
        # - If CompletionModelSettings exists (has_tenant_settings=True): use is_org_enabled
        # - If no tenant settings exist (has_tenant_settings=False): fallback to default_enabled
        if self.has_tenant_settings:
            access_enabled = self.is_org_enabled
            logger.debug(f"Model {self.name}: has_tenant_settings=True, is_org_enabled={access_enabled}")
        else:
            access_enabled = self.default_enabled
            logger.debug(f"Model {self.name}: has_tenant_settings=False, default_enabled={access_enabled}")
            
        is_locked = self.is_locked
        is_deprecated = self.is_deprecated
        can_access = not is_locked and not is_deprecated and access_enabled
        
        return can_access

    def meets_security_classification(
        self, security_classification: Optional["SecurityClassification"] = None
    ):
        if security_classification is None:
            return True
        else:
            if self.security_classification is None:
                return False

            return (
                self.security_classification.security_level
                >= security_classification.security_level
            )
