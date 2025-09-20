import os
import pathlib

import yaml

from intric.ai_models.completion_models.completion_model import (
    CompletionModelCreate,
    CompletionModelUpdate,
)
from intric.ai_models.completion_models.completion_models_repo import (
    CompletionModelsRepository,
)
from intric.ai_models.embedding_models.embedding_model import (
    EmbeddingModelCreate,
    EmbeddingModelUpdate,
)
from intric.ai_models.embedding_models.embedding_models_repo import (
    AdminEmbeddingModelsService,
)
from intric.image_generation_models.domain.image_generation_model import (
    ImageGenerationModelCreate,
    ImageGenerationModelUpdate,
)
from intric.image_generation_models.domain.image_generation_model_repo import (
    ImageGenerationModelRepository,
)
from intric.database.database import sessionmanager
from intric.main.logging import get_logger

COMPLETION_MODELS_FILE_NAME = "ai_models.yml"

logger = get_logger(__name__)


def load_models_from_config():
    config_path = os.path.join(pathlib.Path(__file__).parent.resolve(), COMPLETION_MODELS_FILE_NAME)
    with open(config_path, "r") as file:
        data = yaml.safe_load(file)
        return data


async def create_models(
    models: dict,
    repository: type[CompletionModelsRepository] | type[AdminEmbeddingModelsService],
    model_create: type[CompletionModelCreate] | type[EmbeddingModelCreate],
    model_update: type[CompletionModelUpdate] | type[EmbeddingModelUpdate],
):
    logger.info(f"create_models called with {len(models)} models, repository: {repository.__name__}")

    async with sessionmanager.session() as session, session.begin():
        repository = repository(session=session)
        logger.info(f"Repository instance created: {repository}")

        existing_models = await repository.get_ids_and_names()
        logger.info(f"Found {len(existing_models)} existing models in database")
        existing_models_names = {model.name: model.id for model in existing_models}
        new_models_names = [model["name"] for model in models]
        logger.info(f"New model names from config: {new_models_names}")

        # remove models
        models_to_remove = [model for model in existing_models if model.name not in new_models_names]
        logger.info(f"Models to remove: {[m.name for m in models_to_remove]}")
        for model in models_to_remove:
            logger.info(f"Deleting model: {model.name}")
            await repository.delete_model(model.id)

        # create new models or update existing
        for i, model in enumerate(models):
            logger.info(f"Processing model {i+1}/{len(models)}: {model.get('name', 'UNKNOWN')}")
            try:
                model_instance = model_create(**model)
                logger.info(f"Created model instance: {model_instance}")

                if model_instance.name not in existing_models_names:
                    logger.info(f"Creating new model: {model_instance.name}")
                    result = await repository.create_model(model_instance)
                    logger.info(f"Model creation result: {result}")
                else:
                    logger.info(f"Updating existing model: {model_instance.name}")
                    update_instance = model_update(**model_instance.model_dump(), id=existing_models_names[model_instance.name])
                    result = await repository.update_model(update_instance)
                    logger.info(f"Model update result: {result}")
            except Exception as e:
                logger.error(f"Failed to process model {model.get('name', 'UNKNOWN')}: {str(e)}")
                raise


async def init_models():
    try:
        data = load_models_from_config()

        logger.info("Completion Models initialization...")
        completion_models = data["completion_models"]
        await create_models(
            models=completion_models,
            repository=CompletionModelsRepository,
            model_create=CompletionModelCreate,
            model_update=CompletionModelUpdate,
        )
        logger.info("Completion Models initialization completed.")

        logger.info("Embedding Models initialization...")
        embedding_models = data["embedding_models"]
        await create_models(
            models=embedding_models,
            repository=AdminEmbeddingModelsService,
            model_create=EmbeddingModelCreate,
            model_update=EmbeddingModelUpdate,
        )
        logger.info("Embedding Models initialization completed.")

        logger.info("Image Generation Models initialization...")
        image_generation_models = data.get("image_generation_models", [])
        logger.info(f"Found {len(image_generation_models)} image generation models in config")
        for i, model in enumerate(image_generation_models):
            logger.info(f"Image generation model {i+1}: {model.get('name', 'UNKNOWN')} with family: {model.get('family', 'UNKNOWN')}")

        if not image_generation_models:
            logger.warning("No image generation models found in configuration!")
        else:
            try:
                await create_models(
                    models=image_generation_models,
                    repository=ImageGenerationModelRepository,
                    model_create=ImageGenerationModelCreate,
                    model_update=ImageGenerationModelUpdate,
                )
                logger.info("Image Generation Models initialization completed successfully.")
            except Exception as e:
                logger.error(f"Failed to create image generation models: {str(e)}")
                raise

    except Exception as e:
        logger.exception(f"Creating models crashed with next error: {str(e)}")
