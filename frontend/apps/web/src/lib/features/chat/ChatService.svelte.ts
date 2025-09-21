import { browser } from "$app/environment";
import { PAGINATION } from "$lib/core/constants";
import { createAsyncState } from "$lib/core/helpers/createAsyncState.svelte";
import { createClassContext } from "$lib/core/helpers/createClassContext";
import { waitFor } from "$lib/core/waitFor";
import {
  type ConversationSparse,
  type Assistant,
  type Conversation,
  type GroupChat,
  type Intric,
  type Paginated,
  type UploadedFile,
  type ConversationMessage,
  IntricError,
  type ConversationTools
} from "@intric/intric-js";

export type ChatPartner = GroupChat | Assistant;

export class ChatService {
  #chatPartner = $state<ChatPartner>() as ChatPartner; // Needs typecast to get rid of undefined
  partner = $derived(this.#chatPartner);
  #intric: Intric;
  currentConversation = $state<Conversation>(emptyConversation());
  totalConversations = $state<number>(0);
  loadedConversations = $state<ConversationSparse[]>([]);
  hasMoreConversations = $derived(this.loadedConversations.length < this.totalConversations);
  #nextCursor = $state<string | null>(null);

  constructor(data: Parameters<typeof this.init>[0]) {
    this.#intric = data.intric;
    this.init(data);
  }

  init(data: {
    intric: Intric;
    chatPartner: ChatPartner;
    initialConversation?: Promise<Conversation | null> | Conversation | null;
    initialHistory?: Promise<Paginated<ConversationSparse>> | Paginated<ConversationSparse>;
  }) {
    this.#chatPartner = data.chatPartner;

    waitFor(data.initialHistory, {
      onLoaded: (initialHistory) => {
        this.loadedConversations = initialHistory.items;
        this.totalConversations = initialHistory.total_count;
        this.#nextCursor = initialHistory.next_cursor ?? null;
      }
    });

    waitFor(data.initialConversation, {
      onLoaded: (initialConversation) => {
        this.currentConversation = initialConversation;
      },
      onNull: () => {
        this.currentConversation = emptyConversation();
      }
    });
  }

  newConversation() {
    this.currentConversation = emptyConversation();
  }

  async loadConversations(args?: { limit?: number; reset?: boolean }) {
    try {
      if (args?.reset) {
        this.#nextCursor = null;
      }
      const response = await this.#intric.conversations.list({
        chatPartner: this.#chatPartner,
        pagination: {
          limit: args?.limit ?? PAGINATION.PAGE_SIZE,
          cursor: this.#nextCursor ?? undefined
        }
      });

      if (args?.reset) {
        this.loadedConversations = response.items;
      } else {
        this.loadedConversations.push(...response.items);
      }

      this.#nextCursor = response.next_cursor ?? null;
      this.totalConversations = response.total_count;
      return response;
    } catch (error) {
      console.error("Error loading pagination", error);
    }
  }

  async loadMoreConversations(args?: { limit?: number }) {
    return this.loadConversations(args);
  }

  async reloadHistory() {
    return this.loadConversations({ reset: true });
  }

  async deleteConversation(conversation: { id: string }) {
    try {
      await this.#intric.conversations.delete(conversation);
      this.loadedConversations = this.loadedConversations.filter(
        ({ id }) => id !== conversation.id
      );
      if (this.currentConversation?.id === conversation.id) {
        this.newConversation();
      }
    } catch (e) {
      if (browser) alert(`Error while deleting conversation with id ${conversation.id}`);
      console.error(e);
    }
  }

  async loadConversation(conversation: { id: string }) {
    try {
      const loaded = await this.#intric.conversations.get(conversation);
      this.currentConversation = loaded;
      return loaded;
    } catch (e) {
      if (browser) alert(`Error while loading conversation with id ${conversation.id}`);
      console.error(e);
    }
  }

  changeChatPartner(newPartner: ChatPartner) {
    const oldPartner = this.#chatPartner;
    this.#chatPartner = newPartner;

    if (oldPartner !== newPartner) {
      this.newConversation();
      this.reloadHistory();
    }
  }

  askQuestion = createAsyncState(
    async (
      question: string,
      attachments?: UploadedFile[],
      tools?: ConversationTools,
      useWebSearch?: boolean,
      abortController?: AbortController,
      imageParams?: {
        imageGeneration: boolean;
        imageSize?: string;
      }
    ) => {
      // Debug logging for image parameters
      console.log('[ChatService] askQuestion called with:', {
        question: question.substring(0, 50) + '...',
        hasAttachments: !!attachments?.length,
        hasTools: !!tools,
        useWebSearch,
        imageParams
      });

      this.currentConversation.messages?.push(emptyMessage({ question }));

      const ensureCurrentSession = (event: { session_id: string }) => {
        if (event.session_id !== this.currentConversation.id) {
          abortController?.abort();
          console.error(`cancelled streaming answer as session ${event.session_id} was changed.`);
        }
      };

      try {
        let buffer = "";
        const ref =
          this.currentConversation.messages[this.currentConversation.messages?.length - 1];

        // Build request with optional image parameters
        const requestData: any = {
          question,
          chatPartner: this.#chatPartner,
          conversation: { id: this.currentConversation.id },
          files: (attachments ?? []).map((fileRef) => ({ id: fileRef.id })),
          tools,
          abortController,
          useWebSearch,
        };

        // Add image generation parameters if provided
        if (imageParams?.imageGeneration) {
          console.log('[ChatService] Image generation mode enabled');
          requestData.image_generation = true;

          // Add advanced parameters if size is specified
          if (imageParams.imageSize) {
            requestData.image_generation_params = {
              size: imageParams.imageSize
            };
            console.log('[ChatService] Using image generation params:', requestData.image_generation_params);
          }
        }

        console.log('[ChatService] Calling intric.conversations.ask with:', {
          ...requestData,
          files: requestData.files?.length + ' files'
        });

        await this.#intric.conversations.ask({
          ...requestData,
          callbacks: {
            onFirstChunk: (chunk) => {
              Object.assign(ref, chunk);
              this.currentConversation.id = chunk.session_id;
              this.currentConversation.name = question;
            },
            onText: (text) => {
              ensureCurrentSession(text);
              if (text.answer.includes("<") || buffer) {
                buffer += text.answer;
                if (isNotInref(buffer) || isCompleteInref(buffer)) {
                  ref.answer += buffer;
                  buffer = "";
                }
              } else {
                ref.answer += text.answer;
              }
              ref.references = text.references;
            },
            onImage: (image) => {
              ensureCurrentSession(image);
              Object.assign(ref, image);
            },
            onIntricEvent: (event) => {
              ensureCurrentSession(event);
              if (event.intric_event_type === "generating_image") {
                ref.generated_files.push({ id: "", name: "", mimetype: "", size: 0 });
              }
            }
          }
        });
      } catch (error) {
        const streamAborted = error instanceof Error && error.message.includes("aborted");
        if (streamAborted) {
          console.log('[ChatService] Request was aborted by user');
          return;
        }

        console.error('[ChatService] Error during conversation request:', error);

        let message = "We encountered an error processing your request.";

        if (error instanceof IntricError) {
          console.error('[ChatService] IntricError details:', {
            code: error.code,
            message: error.getReadableMessage(),
            context: error.context
          });
          message += `\n\`\`\`\n${error.code}: "${error.getReadableMessage()}"\n\`\`\``;
        } else if (error instanceof Error) {
          console.error('[ChatService] Error details:', {
            name: error.name,
            message: error.message,
            stack: error.stack
          });
          message += `\n\`\`\`\n${error.name}: "${error.message}"\n\`\`\``;
        } else {
          console.error('[ChatService] Unknown error type:', error);
        }

        // Special handling for image generation errors
        if (imageParams?.imageGeneration && error instanceof Error) {
          if (error.message.includes('Authentication') || error.message.includes('API key')) {
            message = "Image generation failed: Please check your API keys are configured correctly.";
          } else if (error.message.includes('Rate limit')) {
            message = "Image generation failed: Rate limit exceeded. Please try again later.";
          } else if (error.message.includes('Image generation failed')) {
            message = `Image generation error: ${error.message}`;
          }
        }

        this.currentConversation.messages[this.currentConversation.messages?.length - 1].answer = message;
        console.error('[ChatService] Final error message shown to user:', message);
      }

      this.reloadHistory();
    }
  );
}

export const [getChatService, initChatService] = createClassContext("Chat service", ChatService);

function emptyMessage(partial?: Partial<ConversationMessage>): ConversationMessage {
  return {
    generated_files: [],
    question: "",
    answer: "",
    references: [],
    files: [],
    web_search_references: [],
    tools: {
      assistants: []
    },
    ...partial
  };
}

function emptyConversation(): Conversation {
  return {
    id: "",
    name: "New conversation",
    messages: []
  };
}

const couldBeInref = (buffer: string): boolean => {
  // We assume that "<" can be anywhere in the buffer, but that there can only be one
  return "<inref".startsWith(buffer.slice(buffer.indexOf("<"), 5));
};
const isNotInref = (buffer: string): boolean => !couldBeInref(buffer);
const isCompleteInref = (buffer: string): boolean => couldBeInref(buffer) && buffer.includes(">");
