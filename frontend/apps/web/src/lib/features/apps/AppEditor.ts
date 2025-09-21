import { createContext } from "$lib/core/context";
import { createResourceEditor } from "$lib/core/editing/ResourceEditor";
import type { Intric, App } from "@intric/intric-js";

const [getAppEditor, setAppEditor] = createContext<ReturnType<typeof initAppEditor>>("Edit an App");

/**
 * Initialise the ResourceEditor in its context.
 * Retrieve it via `getAppEditor()`
 */
function initAppEditor(data: { app: App; intric: Intric; onUpdateDone?: (app: App) => void }) {
  const editor = createResourceEditor({
    intric: data.intric,
    resource: data.app,
    defaults: {
      prompt: { description: "", text: "" },
      output_type: "text"
    },
    editableFields: {
      name: true,
      description: true,
      completion_model: { id: true },
      completion_model_kwargs: true,
      transcription_model: { id: true },
      attachments: ["id"],
      prompt: { description: true, text: true },
      input_fields: ["type", "description"],
      output_type: true,
      image_generation_model: true
    },
    manageAttachements: "attachments",
    updateResource: async (resource, changes) => {
      console.log('[AppEditor] Before update:', {
        resource_output_type: resource.output_type,
        resource_image_model_id: resource.image_generation_model?.id,
        changes,
        changes_has_output_type: 'output_type' in changes,
        changes_has_image_model: 'image_generation_model' in changes
      });

      const updated = await data.intric.apps.update({ app: resource, update: changes });

      console.log('[AppEditor] After update:', {
        updated_output_type: updated.output_type,
        updated_image_model_id: updated.image_generation_model?.id,
        updated_image_model_full: updated.image_generation_model
      });

      data.onUpdateDone?.(updated);
      return updated;
    }
  });
  setAppEditor(editor);
  return editor;
}
export { initAppEditor, getAppEditor };
