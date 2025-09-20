import type { PageLoad } from "./$types";
import { PAGINATION } from "$lib/core/constants";
import { isValidChatPartnerType } from "$lib/features/chat/isValidChatPartnerType";

export const load: PageLoad = async (event) => {
  const { intric, currentSpace } = await event.parent();

  // Get type from URL parameters
  let partnerType = event.url.searchParams.get("type");

  // In space context, if no type is specified and we have an id parameter,
  // default to "assistant" instead of "default-assistant"
  if (!partnerType) {
    const hasIdParam = event.url.searchParams.get("id");
    if (hasIdParam && !currentSpace.personal) {
      // Non-personal space with id parameter should default to "assistant"
      partnerType = "assistant";
    } else {
      // Default to "default-assistant" for personal spaces or when no id
      partnerType = "default-assistant";
    }
  }

  if (!isValidChatPartnerType(partnerType)) {
    throw new Error("Unknown chat type!");
  }

  const partnerId =
    partnerType === "default-assistant"
      ? currentSpace.default_assistant.id
      : event.url.searchParams.get("id");
  const selectedSessionId = event.url.searchParams.get("session_id");

  if (!partnerId) {
    throw new Error("Not working");
  }

  const getPartner = async () => {
    switch (partnerType) {
      case "assistant":
        return intric.assistants.get({
          id: partnerId
        });
      case "group-chat":
        return intric.groupChats.get({
          id: partnerId
        });
      // instead of case "default-assistant"
      default:
        return currentSpace.default_assistant;
    }
  };

  const loadSession = async () => {
    if (!selectedSessionId) return null;
    return intric.conversations.get({ id: selectedSessionId });
  };

  const listSessions = async () => {
    return (
      intric.conversations
        .list({
          chatPartner: { id: partnerId, type: partnerType },
          pagination: { limit: PAGINATION.PAGE_SIZE }
        })
        // Need to catch the error here, otherwise the app will crash
        .catch((error) => error)
    );
  };

  const partnerPromise = getPartner();
  const historyPromise = listSessions();
  const initialSessionPromise = loadSession();

  const partner = await partnerPromise;

  return {
    chatPartner: partner,
    initialHistory: historyPromise,
    initialConversation: initialSessionPromise
  };
};
